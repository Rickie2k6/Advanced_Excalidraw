"""Shared prompts, output contracts, caching, and provider request logging."""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path

from app.core.config import BACKEND_DIR

logger = logging.getLogger(__name__)
IMAGE_ANALYSIS_DIR = BACKEND_DIR / "data/whiteboard_image_analysis"

IMAGE_PROMPT = (
    "Analyze this image that was inserted on an Excalidraw whiteboard. "
    "Describe what the image shows, identify important objects, extract visible "
    "text, and explain important visual relationships. Only describe information "
    "visible in the image."
)
TARGET_SYSTEM = (
    "You extract visual actions and targets from whiteboard commands. Return JSON only.\n\n"
    'Required format:\n{\n  "action": "circle",\n  "target_description": "happy face",\n  "label": "HAPPY"\n}\n\n'
    "For a labeled feeling chart, return the exact printed feeling name in label. "
    "Use null for label when no unique printed label matches. "
    "For commands that do not request a visual action, use null for action. "
    "Never return row or column numbers or pixel positions. "
    "The target_description must be a short visual phrase suitable for an object "
    "localization model. Do not include coordinates."
)
CANDIDATE_SYSTEM = (
    "You select the object detection candidate that best matches the user's requested visual target.\n"
    "Inspect the image and compare all candidate bounding boxes.\n"
    'Return JSON only in this format:\n{"candidate_index": 0}\n'
    "Do not invent a new bounding box."
)


def save_response(log_file, provider, model, operation, prompt, system, image_path, metadata, response, output):
    """Keep provider attribution and the existing request/response log structure."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "operation": operation,
        "request": {
            "model": model,
            "input": prompt,
            **(metadata or {}),
        },
        "response": {
            "response_id": response.id,
            "request_id": getattr(response, "_request_id", None),
            "output": output,
            "usage": response.usage.model_dump() if response.usage else None,
        },
    }
    if system:
        entry["request"]["system"] = system
    if image_path:
        entry["request"]["image_path"] = image_path
    path = Path(log_file)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        # A completed paid request must not be retried solely because logging failed.
        logger.warning("Could not write %s request log for %s", provider, operation)


def parse_json_response(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```") and "\n" in raw:
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object from the LLM.")
    return value


def generate_reply(request, question: str, whiteboard_context: str) -> str:
    prompt = (
        "\nYou are an assistant integrated into Excalidraw.\n\n"
        f"The user asked:\n{question}\n\n"
        f"The current whiteboard analysis is:\n{whiteboard_context}\n\n"
        "Answer the user's question using the whiteboard context when relevant.\n"
    )
    return request(prompt, operation="generate_reply", metadata={
        "question": question, "whiteboard_context": whiteboard_context,
    })


def analyze_inserted_image(request, provider: str, model: str, image_path: str, file_id: str) -> str:
    # Separate providers so fallback cannot accidentally reuse another provider's result.
    cache_path = IMAGE_ANALYSIS_DIR / provider / f"{file_id}.json"
    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if cached.get("model") == model:
            logger.info("Image analysis cache hit: provider=%s file_id=%s", provider, file_id)
            return cached["analysis"]
    path = Path(image_path)
    if not path.is_file():
        raise FileNotFoundError(f"Image not found: {path}")
    analysis = request(IMAGE_PROMPT, image_path=image_path,
                       operation="analyze_inserted_image", metadata={"file_id": file_id})
    result = {
        "file_id": file_id, "image_path": str(path), "analysis": analysis,
        "provider": provider, "model": model,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        logger.warning("Could not cache image analysis: provider=%s file_id=%s", provider, file_id)
    return analysis


def extract_visual_target(request, question: str, image_analysis: str) -> dict:
    raw = request(f"User command:\n{question}\n\nImage description:\n{image_analysis}",
                  system=TARGET_SYSTEM, operation="extract_visual_target")
    # Invalid output raises so the router can try the other provider.
    result = parse_json_response(raw)
    for field in ("action", "target_description"):
        if field not in result or (result[field] is not None and not isinstance(result[field], str)):
            raise ValueError(f"Invalid visual target field: {field}")
    target = {"action": result["action"], "target_description": result["target_description"]}
    if "label" in result:
        label = result["label"]
        if label is not None and not isinstance(label, str):
            raise ValueError("Invalid visual target field: label")
        target["label"] = label.strip().upper() if isinstance(label, str) else None
    return target


def select_visual_candidate(request, question: str, target_description: str,
                            detections: list[dict], image_path: str) -> dict:
    candidate_text = "\n".join(
        f"Candidate {i}: bbox={d['bbox']}, label={d['label']}, score={d['score']}"
        for i, d in enumerate(detections)
    )
    prompt = (f"User request:\n{question}\n\nTarget:\n{target_description}\n\n"
              f"Detection candidates:\n{candidate_text}")
    raw = request(prompt, system=CANDIDATE_SYSTEM, image_path=image_path,
                  operation="select_visual_candidate")
    result = parse_json_response(raw)
    index = result.get("candidate_index")
    if type(index) is not int or not 0 <= index < len(detections):
        raise ValueError("Invalid candidate_index returned by the LLM.")
    return {**detections[index], "candidate_index": index}
