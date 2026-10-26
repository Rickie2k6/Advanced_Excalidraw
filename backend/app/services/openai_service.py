"""Openai adapter for the shared whiteboard LLM contract."""

import base64
import mimetypes
import os
from pathlib import Path

from app.core.config import BACKEND_DIR, settings
from app.services import llm_common as common

__all__ = ["generate_reply", "analyze_inserted_image", "extract_visual_target", "select_visual_candidate"]
LOG_FILE = BACKEND_DIR / "logs/openai_requests.jsonl"


def _model() -> str:
    return settings.openai_model


def get_client():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("Set OPENAI_API_KEY in backend/.env before using OpenAI.")
    from openai import OpenAI
    return OpenAI(api_key=api_key)


def _request(prompt, *, system="", image_path=None, operation, metadata=None) -> str:
    content = [{"type": "input_text", "text": prompt}]
    if image_path:
        path = Path(image_path)
        mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
        encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
        content.append({"type": "input_image", "image_url": f"data:{mime_type};base64,{encoded}",
                        "detail": "high"})
    payload = {"model": _model(), "input": [{"role": "user", "content": content}]}
    if system:
        payload["instructions"] = system
    with get_client() as client:
        response = client.responses.create(**payload)
    if getattr(response, "status", None) in ("incomplete", "failed", "cancelled"):
        raise ValueError("OpenAI did not complete the response.")
    output = response.output_text
    if not output or not output.strip():
        raise ValueError("OpenAI returned no text.")
    common.save_response(LOG_FILE, "openai", _model(), operation, prompt, system,
                         image_path, metadata, response, output)
    return output


def generate_reply(question: str, whiteboard_context: str) -> str:
    return common.generate_reply(_request, question, whiteboard_context)


def analyze_inserted_image(image_path: str, file_id: str) -> str:
    return common.analyze_inserted_image(_request, "openai", _model(), image_path, file_id)


def extract_visual_target(question: str, image_analysis: str) -> dict:
    return common.extract_visual_target(_request, question, image_analysis)


def select_visual_candidate(question: str, target_description: str,
                            detections: list[dict], image_path: str) -> dict:
    return common.select_visual_candidate(_request, question, target_description, detections, image_path)
