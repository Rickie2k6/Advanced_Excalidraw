import json
import re
import base64

from PIL import Image

from app.core.paths import WHITEBOARD_IMAGES_DIR

from app.services.feeling_chart import is_known_feeling_chart, resolve_feeling_label
from app.services.question_solver import solve_question_request
from app.services.math_agent import solve_linear_steps
from app.services.math_commands import extract_write_math_action
from app.services.whiteboard_math import extract_whiteboard_solve_action
from app.services.equation_context import load_equations
from app.services.visual_geometry import (
    image_bbox_to_excalidraw,
)

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from starlette.concurrency import (
    run_in_threadpool,
)

from app.core.state_store import (
    update_analysis,
    update_scene,
)

from app.schemas.analysis import (
    ChatResponse,
)

from app.services.paddle.analyzer import (
    analyze_whiteboard,
)

from app.services.paddle.formatter import (
    format_analysis,
)

from app.services.equation_context import (
    build_equation_context,
)

from app.utils.images import (
    upload_to_image,
)

from app.services.llm_service import (
    generate_reply,
    analyze_inserted_image,
    extract_visual_target,
    select_visual_candidate,
)


def detect_target(*args):
    # Load the detector only for visual requests, never during API startup.
    from app.services.detector import detect_target as detect
    return detect(*args)


router = APIRouter()


# ============================================================
# WRITE MATH ACTION
# ============================================================

def extract_solve_math_action(question: str):
    match = re.fullmatch(
        r"\s*(?:please\s+)?(?:giải(?: phương trình)?|solve(?: the equation)?)"
        r"\s*[:：]?\s*(.+?)\s*[.]?\s*",
        question,
        re.IGNORECASE,
    )

    if not match:
        return None

    expression = match.group(1).strip()

    if "=" not in expression:
        return None

    try:
        return solve_linear_steps(expression)

    except ValueError as error:
        print(
            "[Math Agent] Unsupported equation:",
            error,
        )
        return None

@router.post(
    "/chat",
    response_model=ChatResponse,
)
async def chat(
    question: str = Form(...),

    # Whiteboard image is optional.
    whiteboard: UploadFile | None = File(
        None
    ),

    scene_json: str | None = Form(
        None
    ),
):
    # ============================================================
    # 1. SCENE JSON
    # ============================================================

    scene = None

    if scene_json:
        try:
            scene = json.loads(
                scene_json
            )

        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail=(
                    "scene_json is not "
                    "valid JSON."
                ),
            )

        elements = scene.get("elements", []) if isinstance(scene, dict) else scene
        if (not isinstance(elements, list) or
                any(not isinstance(element, dict) for element in elements) or
                (isinstance(scene, dict) and not isinstance(scene.get("files", {}), dict))):
            raise HTTPException(status_code=400, detail="scene_json must contain elements and optional files.")

        update_scene(
            scene
        )

    if scene is not None:
        if isinstance(scene, dict):
            debug_elements = scene.get(
                "elements",
                [],
            )

        elif isinstance(scene, list):
            debug_elements = scene

        else:
            debug_elements = []

        print(
            "[CHAT SCENE]",
            len(debug_elements),
            "elements",
        )

        for element in debug_elements:
            print(
                "[CHAT ELEMENT]",
                {
                    "id": element.get("id"),
                    "type": element.get("type"),
                    "x": element.get("x"),
                    "y": element.get("y"),
                    "width": element.get("width"),
                    "height": element.get("height"),
                    "text": element.get("text"),
                    "isDeleted": element.get(
                        "isDeleted",
                        False,
                    ),
                },
            )

    else:
        print(
            "[CHAT SCENE] scene_json is NONE"
        )

    # Explicit commands have one backend handling path and require no OCR/LLM.
    visual_action = extract_write_math_action(question)
    if visual_action is None:
        visual_action = extract_solve_math_action(question)

        # "solve question 2": find the question on the worksheet and write in its empty space.
    if visual_action is None:
        question_result = await solve_question_request(question, scene)
        if question_result is not None:
            return {
                "question": question,
                "answer": question_result.message,
                "analysis": None,
                "visual_action": question_result.action,
            }
    if visual_action is None:
        visual_action = extract_whiteboard_solve_action(question, load_equations())
    if visual_action is not None:
        return {
            "question": question,
            "answer": "",  # The widget confirms only after the canvas commit succeeds.
            "analysis": None,
            "visual_action": visual_action,
        }

    # ============================================================
    # 2. OPTIONAL FULL-WHITEBOARD ANALYSIS
    # ============================================================

    if whiteboard is not None:
        image = await upload_to_image(
            whiteboard
        )

        try:
            analysis = await run_in_threadpool(analyze_whiteboard, image)
            update_analysis(analysis)
            formatted_analysis = format_analysis(analysis)
        except Exception as error:
            analysis = None
            formatted_analysis = f"Full-whiteboard OCR unavailable: {error}"

    else:
        analysis = None

        # Important:
        # No image does NOT mean the whiteboard
        # is empty because equations.json may
        # already contain recognized equations.
        formatted_analysis = (
            "No full-whiteboard image was "
            "provided with this chat request."
        )

    # ============================================================
    # 3. LOAD RECOGNIZED EQUATIONS FROM equations.json
    # ============================================================

    equation_context = (
        await run_in_threadpool(
            build_equation_context
        )
    )

    # ============================================================
    # 4. INITIAL VISUAL ACTION
    # ============================================================

    # Explicit commands were handled above. Only screenshot/group OCR can
    # provide a new solve action at this point.
    visual_action = extract_whiteboard_solve_action(
        question, load_equations(), analysis,
    )

    if visual_action:
        print(
            "[Write Math Action]",
            visual_action,
        )

    # ============================================================
    # 5. INSERTED IMAGE ANALYSIS
    # ============================================================

    inserted_image_context = (
        "No inserted images are currently "
        "available on the whiteboard."
    )

    if scene is not None:

        # scene_json may be:
        #
        # {
        #     "elements": [...],
        #     "files": {...}
        # }
        #
        # or directly [...]

        if isinstance(scene, dict):
            elements = scene.get(
                "elements",
                [],
            )

            files = scene.get(
                "files",
                {},
            )

        elif isinstance(scene, list):
            elements = scene
            files = {}

        else:
            elements = []
            files = {}

        # --------------------------------------------------------
        # Find Excalidraw image elements
        # --------------------------------------------------------

        image_elements = [
            element
            for element in elements
            if (
                element.get("type")
                == "image"

                and not element.get(
                    "isDeleted",
                    False,
                )

                and element.get(
                    "fileId"
                )
            )
        ]

        # --------------------------------------------------------
        # DEBUG: Excalidraw image geometry
        # --------------------------------------------------------

        for image_element in image_elements:
            print(
                "[Excalidraw Image Element]",
                {
                    "id":
                        image_element.get(
                            "id"
                        ),

                    "fileId":
                        image_element.get(
                            "fileId"
                        ),

                    "x":
                        image_element.get(
                            "x"
                        ),

                    "y":
                        image_element.get(
                            "y"
                        ),

                    "width":
                        image_element.get(
                            "width"
                        ),

                    "height":
                        image_element.get(
                            "height"
                        ),

                    "scale":
                        image_element.get(
                            "scale"
                        ),

                    "angle":
                        image_element.get(
                            "angle"
                        ),

                    "crop":
                        image_element.get(
                            "crop"
                        ),
                },
            )

        # The same image may appear multiple
        # times on the canvas.
        #
        # Analyze each file only once.

        file_ids = list(
            dict.fromkeys(
                element["fileId"]
                for element
                in image_elements
            )
        )

        image_context_parts = []

        image_directory = WHITEBOARD_IMAGES_DIR

        # ========================================================
        # PROCESS EACH UNIQUE IMAGE FILE
        # ========================================================

        for file_id in file_ids:

            image_path = None

            # ----------------------------------------------------
            # A. Try actual Excalidraw image from scene.files
            # ----------------------------------------------------

            file_data = files.get(
                file_id
            )

            if file_data:
                data_url = file_data.get(
                    "dataURL"
                )

                if data_url:
                    try:
                        match = re.match(
                            (
                                r"data:"
                                r"(image/[^;]+);"
                                r"base64,(.+)"
                            ),
                            data_url,
                            re.DOTALL,
                        )

                        if match:
                            mime_type = (
                                match.group(1)
                            )

                            encoded_data = (
                                match.group(2)
                            )

                            image_bytes = (
                                base64.b64decode(
                                    encoded_data
                                )
                            )

                            extension_map = {
                                "image/png":
                                    ".png",

                                "image/jpeg":
                                    ".jpg",

                                "image/webp":
                                    ".webp",
                            }

                            extension = (
                                extension_map.get(
                                    mime_type,
                                    ".png",
                                )
                            )

                            image_directory.mkdir(
                                parents=True,
                                exist_ok=True,
                            )

                            image_path = (
                                image_directory
                                / (
                                    f"{file_id}"
                                    f"{extension}"
                                )
                            )

                            image_path.write_bytes(
                                image_bytes
                            )

                    except Exception as error:
                        print(
                            "[Chatbot] Failed "
                            "to decode scene "
                            f"image {file_id}:",
                            error,
                        )

            # ----------------------------------------------------
            # B. Fallback to existing backend storage
            # ----------------------------------------------------

            if image_path is None:

                image_matches = list(
                    image_directory.glob(
                        f"{file_id}.*"
                    )
                )

                if image_matches:
                    image_path = (
                        image_matches[0]
                    )

            # ----------------------------------------------------
            # C. Image still unavailable
            # ----------------------------------------------------

            if image_path is None:

                image_context_parts.append(
                    (
                        f"Image {file_id}: "
                        "image file was not "
                        "found in scene data "
                        "or backend storage."
                    )
                )

                continue

            # ----------------------------------------------------
            # ORIGINAL IMAGE DIMENSIONS
            # ----------------------------------------------------

            try:
                with Image.open(
                    image_path
                ) as img:
                    (
                        original_width,
                        original_height,
                    ) = img.size

                print(
                    "[Original Image Size]",
                    {
                        "width":
                            original_width,

                        "height":
                            original_height,
                    },
                )

            except Exception as error:
                print(
                    "[Original Image Size] "
                    "ERROR:",
                    repr(error),
                )

                original_width = None
                original_height = None

            # ----------------------------------------------------
            # D. Vision analysis
            # ----------------------------------------------------

            try:
                print(
                    "[Inserted Image] "
                    "analyzing:",
                    file_id,
                    image_path,
                )

                image_analysis = (
                    await run_in_threadpool(
                        analyze_inserted_image,
                        str(image_path),
                        file_id,
                    )
                )

                # -----------------------------------------------
                # Extract requested visual target
                # -----------------------------------------------

                visual_target = (
                    await run_in_threadpool(
                        extract_visual_target,
                        question,
                        image_analysis,
                    )
                )

                print(
                    "[Visual Target]",
                    visual_target,
                )

                target_description = (
                    visual_target.get(
                        "target_description"
                    )
                )

                # -----------------------------------------------
                # Grounding DINO
                # -----------------------------------------------

                detections = []

                known_chart = is_known_feeling_chart(str(image_path))
                chart_detection = (
                    resolve_feeling_label(visual_target.get("label"))
                    if known_chart and visual_target.get("action") == "circle"
                    else None
                )

                if (target_description and not known_chart
                        and visual_target.get("action") == "circle"):
                    detections = (
                        await run_in_threadpool(
                            detect_target,
                            str(image_path),
                            target_description,
                        )
                    )

                print(
                    "[Grounding DINO]",
                    detections,
                )

                # -----------------------------------------------
                # Select correct DINO candidate
                # -----------------------------------------------

                selected_detection = chart_detection

                if known_chart:
                    print("[Feeling Chart] Label lookup:", selected_detection)

                elif not detections:
                    print(
                        "[Selected Detection] "
                        "No Grounding DINO "
                        "candidates."
                    )

                elif not known_chart:
                    selected_detection = (
                        await run_in_threadpool(
                            select_visual_candidate,
                            question,
                            target_description,
                            detections,
                            str(image_path),
                        )
                    )

                    print(
                        "[Selected Detection]",
                        selected_detection,
                    )

                matching_image_element = next(
                    (
                        element
                        for element
                        in image_elements
                        if (
                            element.get(
                                "fileId"
                            )
                            == file_id
                        )
                    ),
                    None,
                )

                if (
                    selected_detection
                    is not None

                    and matching_image_element
                    is not None

                    and original_width
                    is not None

                    and original_height
                    is not None
                ):
                    excalidraw_target = (
                        image_bbox_to_excalidraw(
                            selected_detection[
                                "bbox"
                            ],
                            matching_image_element,
                            original_width,
                            original_height,
                        )
                    )

                    print(
                        "[Excalidraw Target]",
                        excalidraw_target,
                    )

                    # Only create the image-related
                    # visual action if write_math
                    # has not already been selected.
                    if visual_action is None and visual_target.get("action") == "circle":
                        visual_action = {
                            "action":
                                visual_target.get(
                                    "action"
                                ),

                            "x":
                                excalidraw_target[
                                    "x"
                                ],

                            "y":
                                excalidraw_target[
                                    "y"
                                ],

                            "width":
                                excalidraw_target[
                                    "width"
                                ],

                            "height":
                                excalidraw_target[
                                    "height"
                                ],
                        }

                # -----------------------------------------------
                # Vision result
                # -----------------------------------------------

                print(
                    "[Inserted Image] result:",
                    image_analysis,
                )

                # -----------------------------------------------
                # Add analysis to chatbot context
                # -----------------------------------------------

                image_context_parts.append(
                    f"""
Image file ID:
{file_id}

Vision analysis:
{image_analysis}
""".strip()
                )

            except Exception as error:
                print(
                    "[Inserted Image] ERROR:",
                    repr(error),
                )

                image_context_parts.append(
                    (
                        f"Image {file_id}: "
                        f"analysis failed: "
                        f"{error}"
                    )
                )

        # IMPORTANT:
        # This must be OUTSIDE the file_id loop
        # and OUTSIDE the except block.

        if image_context_parts:
            inserted_image_context = (
                "\n\n".join(
                    image_context_parts
                )
            )

    # ============================================================
    # 6. BUILD CHATBOT CONTEXT
    # ============================================================

    combined_context = f"""
CURRENT WHITEBOARD CONTEXT

Recognized equation data:
{equation_context}

Additional full-whiteboard analysis:
{formatted_analysis}

Inserted image analysis:
{inserted_image_context}

IMPORTANT:
- The recognized equation data above comes from the
  equation-group OCR pipeline and equations.json.

- When answering questions about mathematical
  equations currently written on the whiteboard,
  prefer the recognized equation data above.

- The additional full-whiteboard analysis describes
  visual content detected from an exported image of
  the whole whiteboard, when such an image was
  provided with the chat request.

- The inserted image analysis describes image
  elements that were inserted directly onto the
  Excalidraw whiteboard.

- When the user refers to an image, picture, photo,
  chart, diagram, screenshot, or other inserted
  visual content, use the inserted image analysis
  when relevant.

- An inserted image may be represented by an
  Excalidraw file ID. Use the analysis associated
  with that file ID to understand the content of
  the image.

- If multiple image elements reference the same
  file ID, they represent multiple instances of
  the same underlying image asset.

- Use spatial information from the scene when
  available to distinguish objects or images by
  position, such as left, right, above, below,
  or relative placement.

- Do not assume that the absence of a
  full-whiteboard image means that the whiteboard
  is empty. Recognized equations and inserted
  images may still be available independently.

- Do not invent equations, objects, text, image
  contents, or visual relationships that are not
  present in the provided context.

- If the provided context is insufficient to answer
  the user's question confidently, clearly state
  that the available whiteboard information is
  insufficient rather than guessing.

- Answer naturally and directly based on the
  user's question and the available whiteboard
  context.
""".strip()

    # ============================================================
    # 7. LLM RESPONSE
    # ============================================================

    if visual_action is not None:
        answer = ""
    elif re.match(r"\s*(?:please\s+|can you\s+)?(?:circle|encircle|khoanh)\b", question, re.IGNORECASE):
        answer = (
            "I couldn't locate a target to circle. Make sure the image is on the "
            "canvas and describe the target clearly. If this persists, check the "
            "backend image-analysis and detector logs."
        )
    else:
        answer = await run_in_threadpool(
            generate_reply, question, combined_context,
        )
    print("[CHAT DEBUG] Question:", question)
    print("[CHAT DEBUG] Visual action:", visual_action)
    # ============================================================
    # 8. RESPONSE
    # ============================================================

    return {
        "question":
            question,

        "answer":
            answer,

        "analysis":
            analysis,

        "visual_action":
            visual_action,
    }
