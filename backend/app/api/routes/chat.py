import json

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

from app.services.openai_service import (
    generate_reply,
)


router = APIRouter()


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

        update_scene(
            scene
        )


    # ============================================================
    # 2. OPTIONAL FULL-WHITEBOARD ANALYSIS
    # ============================================================

    if whiteboard is not None:
        image = await upload_to_image(
            whiteboard
        )

        analysis = (
            await run_in_threadpool(
                analyze_whiteboard,
                image,
            )
        )

        update_analysis(
            analysis
        )

        formatted_analysis = (
            format_analysis(
                analysis
            )
        )

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
    # 4. BUILD CHATBOT CONTEXT
    # ============================================================

    combined_context = f"""
CURRENT WHITEBOARD CONTEXT

Recognized equation data:
{equation_context}

Additional full-whiteboard analysis:
{formatted_analysis}

IMPORTANT:
- The recognized equation data above comes from the
  equation-group OCR pipeline and equations.json.
- When answering questions about mathematical
  equations currently written on the board, prefer
  the recognized equation data above.
- Do not invent equations that are not present in
  the provided context.
""".strip()


    # ============================================================
    # 5. OPENAI RESPONSE
    # ============================================================

    answer = await run_in_threadpool(
        generate_reply,
        question,
        combined_context,
    )


    return {
        "question":
            question,

        "answer":
            answer,

        "analysis":
            analysis,
    }