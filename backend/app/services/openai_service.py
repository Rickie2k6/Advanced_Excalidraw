import base64
import mimetypes
from pathlib import Path
from datetime import datetime, timezone
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)
client = OpenAI()

LOG_FILE = "logs/openai_requests.jsonl"


def save_log(data: dict):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                data,
                ensure_ascii=False,
            )
            + "\n"
        )


def generate_reply(
    question: str,
    whiteboard_context: str,
) -> str:

    prompt = f"""
You are an assistant integrated into Excalidraw.

The user asked:
{question}

The current whiteboard analysis is:
{whiteboard_context}

Answer the user's question using the whiteboard context when relevant.
"""

    response = client.responses.create(
        model="gpt-5.6-terra",
        input=prompt,
    )

    answer = response.output_text

    # -----------------------
    # Save log
    # -----------------------

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),

        "request": {
            "model": "gpt-5.6-terra",
            "question": question,
            "whiteboard_context": whiteboard_context,
            "input": prompt,
        },

        "response": {
            "response_id": response.id,
            "request_id": response._request_id,
            "output": answer,
            "usage": (
                response.usage.model_dump()
                if response.usage
                else None
            ),
        },
    }

    save_log(log_entry)

    return answer

IMAGE_ANALYSIS_DIR = Path(
    "data/whiteboard_image_analysis"
)

IMAGE_ANALYSIS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


def analyze_inserted_image(
    image_path: str,
    file_id: str,
) -> str:
    """
    Analyze an image inserted into Excalidraw.

    The result is cached by Excalidraw file_id so the
    same image is not sent to the vision model again
    for every chat message.
    """

    cache_path = (
        IMAGE_ANALYSIS_DIR /
        f"{file_id}.json"
    )

    # ============================================================
    # 1. RETURN CACHED ANALYSIS
    # ============================================================

    if cache_path.exists():
        with open(
            cache_path,
            "r",
            encoding="utf-8",
        ) as f:
            cached = json.load(f)

        return cached["analysis"]

    # ============================================================
    # 2. LOAD IMAGE
    # ============================================================

    path = Path(image_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Image not found: {path}"
        )

    mime_type = (
        mimetypes.guess_type(path.name)[0]
        or "image/png"
    )

    image_bytes = path.read_bytes()

    image_base64 = base64.b64encode(
        image_bytes
    ).decode("utf-8")

    data_url = (
        f"data:{mime_type};base64,"
        f"{image_base64}"
    )

    # ============================================================
    # 3. SEND IMAGE TO VISION MODEL
    # ============================================================

    response = client.responses.create(
        model="gpt-5.6-terra",

        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Analyze this image that was "
                            "inserted on an Excalidraw "
                            "whiteboard. "
                            "Describe what the image shows, "
                            "identify important objects, "
                            "extract visible text, and explain "
                            "important visual relationships. "
                            "Only describe information visible "
                            "in the image."
                        ),
                    },
                    {
                        "type": "input_image",
                        "image_url": data_url,
                        "detail": "high",
                    },
                ],
            }
        ],
    )

    analysis = response.output_text

    # ============================================================
    # 4. CACHE RESULT
    # ============================================================

    result = {
        "file_id": file_id,
        "image_path": str(path),
        "mime_type": mime_type,
        "analysis": analysis,
        "response_id": response.id,
        "timestamp":
            datetime.now(
                timezone.utc
            ).isoformat(),
    }

    with open(
        cache_path,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            result,
            f,
            ensure_ascii=False,
            indent=2,
        )

    return analysis

def extract_visual_target(
    question: str,
    image_analysis: str,
) -> dict:
    """
    Convert a user's whiteboard instruction into a
    structured visual action and target description.
    """

    response = client.responses.create(
        model="gpt-5.6-terra",

        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "You extract visual actions and "
                            "targets from whiteboard commands. "
                            "Return JSON only.\n\n"
                            "Required format:\n"
                            "{\n"
                            '  "action": "circle",\n'
                            '  "target_description": "happy face"\n'
                            "}\n\n"
                            "The target_description must be a "
                            "short visual phrase suitable for "
                            "an object localization model. "
                            "Do not include coordinates."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            f"User command:\n{question}\n\n"
                            "Image description:\n"
                            f"{image_analysis}"
                        ),
                    }
                ],
            },
        ],
    )

    raw = response.output_text.strip()

    try:
        return json.loads(raw)

    except json.JSONDecodeError:
        return {
            "action": None,
            "target_description": None,
        }

def select_visual_candidate(
    question: str,
    target_description: str,
    detections: list[dict],
    image_path: str,
) -> dict:
    path = Path(image_path)

    mime_type = (
        mimetypes.guess_type(path.name)[0]
        or "image/png"
    )

    image_base64 = base64.b64encode(
        path.read_bytes()
    ).decode("utf-8")

    data_url = (
        f"data:{mime_type};base64,{image_base64}"
    )

    candidate_text = "\n".join(
        (
            f"Candidate {i}: "
            f"bbox={d['bbox']}, "
            f"label={d['label']}, "
            f"score={d['score']}"
        )
        for i, d in enumerate(detections)
    )

    response = client.responses.create(
        model="gpt-5.6-terra",
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "You select the object detection "
                            "candidate that best matches the "
                            "user's requested visual target.\n"
                            "Inspect the image and compare all "
                            "candidate bounding boxes.\n"
                            "Return JSON only in this format:\n"
                            '{"candidate_index": 0}\n'
                            "Do not invent a new bounding box."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            f"User request:\n{question}\n\n"
                            f"Target:\n{target_description}\n\n"
                            "Detection candidates:\n"
                            f"{candidate_text}"
                        ),
                    },
                    {
                        "type": "input_image",
                        "image_url": data_url,
                        "detail": "high",
                    },
                ],
            },
        ],
    )

    raw = response.output_text.strip()

    try:
        result = json.loads(raw)
        index = result["candidate_index"]

        if not isinstance(index, int):
            raise ValueError(
                "candidate_index is not an integer"
            )

        if index < 0 or index >= len(detections):
            raise ValueError(
                "candidate_index out of range"
            )

        return {
            "candidate_index": index,
            **detections[index],
        }

    except Exception as error:
        raise ValueError(
            f"Failed to select visual candidate: {error}"
        )