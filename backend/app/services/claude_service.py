"""Claude adapter for the shared whiteboard LLM contract."""

import base64
import mimetypes
import os
from pathlib import Path

from app.core.config import BACKEND_DIR, settings
from app.services import llm_common as common

__all__ = ["generate_reply", "analyze_inserted_image", "extract_visual_target", "select_visual_candidate"]
LOG_FILE = BACKEND_DIR / "logs/claude_requests.jsonl"


MAX_TOKENS = 4096


def _model() -> str:
    return os.getenv("CLAUDE_MODEL") or "claude-sonnet-4-6"


def get_client():
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip() or os.getenv("CLAUDE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("Set ANTHROPIC_API_KEY or CLAUDE_API_KEY in backend/.env before using Claude.")
    from anthropic import Anthropic
    return Anthropic(api_key=api_key)


def _request(prompt, *, system="", image_path=None, operation, metadata=None) -> str:
    content = [{"type": "text", "text": prompt}]
    if image_path:
        path = Path(image_path)
        mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
        encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
        content.append({"type": "image", "source": {
            "type": "base64", "media_type": mime_type, "data": encoded,
        }})
    payload = {"model": _model(), "messages": [{"role": "user", "content": content}],
               "max_tokens": MAX_TOKENS}
    if system:
        payload["system"] = system
    with get_client() as client:
        response = client.messages.create(**payload)
    if response.stop_reason == "max_tokens":
        raise ValueError("Claude response was truncated; increase MAX_TOKENS.")
    output = "".join(block.text for block in response.content if block.type == "text")
    if not output or not output.strip():
        raise ValueError("Claude returned no text.")
    common.save_response(LOG_FILE, "claude", _model(), operation, prompt, system,
                         image_path, metadata, response, output)
    return output


def generate_reply(question: str, whiteboard_context: str) -> str:
    return common.generate_reply(_request, question, whiteboard_context)


def analyze_inserted_image(image_path: str, file_id: str) -> str:
    return common.analyze_inserted_image(_request, "claude", _model(), image_path, file_id)


def extract_visual_target(question: str, image_analysis: str) -> dict:
    return common.extract_visual_target(_request, question, image_analysis)


def select_visual_candidate(question: str, target_description: str,
                            detections: list[dict], image_path: str) -> dict:
    return common.select_visual_candidate(_request, question, target_description, detections, image_path)
