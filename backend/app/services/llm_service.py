"""Route every whiteboard LLM operation using the configured API keys."""

import importlib
import logging
import os

from app.core.config import settings

logger = logging.getLogger(__name__)
__all__ = ["generate_reply", "analyze_inserted_image", "extract_visual_target", "select_visual_candidate"]


def _providers() -> list[str]:
    openai = bool(os.getenv("OPENAI_API_KEY", "").strip())
    claude = bool(os.getenv("ANTHROPIC_API_KEY", "").strip() or os.getenv("CLAUDE_API_KEY", "").strip())
    if not openai and not claude:
        raise ValueError(
            "Set OPENAI_API_KEY or ANTHROPIC_API_KEY (or CLAUDE_API_KEY) in backend/.env."
        )
    if openai and claude:
        preferred = settings.llm_provider.strip().lower()
        if preferred not in ("openai", "claude", "anthropic"):
            raise ValueError("LLM_PROVIDER must be 'openai', 'claude', or 'anthropic' in backend/.env.")
        return ["openai", "claude"] if preferred == "openai" else ["claude", "openai"]
    return ["openai"] if openai else ["claude"]


def _call(operation, *args):
    providers = _providers()
    for index, provider in enumerate(providers):
        try:
            module = importlib.import_module(f"app.services.{provider}_service")
            result = getattr(module, operation)(*args)
        except Exception as error:
            if index + 1 == len(providers):
                raise
            # Avoid printing exception messages that may contain credentials or request data.
            logger.warning("LLM %s failed with %s using %s; retrying with %s",
                           operation, type(error).__name__, provider, providers[index + 1])
        else:
            logger.info("LLM %s handled by provider=%s", operation, provider)
            return result


def generate_reply(question: str, whiteboard_context: str) -> str:
    return _call("generate_reply", question, whiteboard_context)


def analyze_inserted_image(image_path: str, file_id: str) -> str:
    return _call("analyze_inserted_image", image_path, file_id)


def extract_visual_target(question: str, image_analysis: str) -> dict:
    return _call("extract_visual_target", question, image_analysis)


def select_visual_candidate(question: str, target_description: str,
                            detections: list[dict], image_path: str) -> dict:
    return _call("select_visual_candidate", question, target_description, detections, image_path)
