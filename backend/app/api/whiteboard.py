import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.reasoning.equation_adapter import adapt_equations_json
from app.reasoning.pipeline import analyze_equations
from app.services.whiteboard_action_logger import (
    log_whiteboard_action,
)


router = APIRouter(
    prefix="/api/whiteboard",
    tags=["whiteboard"],
)


EQUATIONS_PATH = Path(
    "/home/student/chuynh/Chatbot/data/equations.json"
)


class WhiteboardAction(BaseModel):
    action: str
    element_id: str | None = None
    element_type: str | None = None
    data: dict[str, Any] | None = None


@router.get("/hints")
def get_whiteboard_hints():
    """
    Read the latest whiteboard equations and return
    verified next-step tutoring hints.
    """

    if not EQUATIONS_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="equations.json was not found.",
        )

    try:
        with EQUATIONS_PATH.open(
            "r",
            encoding="utf-8",
        ) as f:
            data = json.load(f)

        equations = adapt_equations_json(data)

        result = analyze_equations(equations)

        return {
            "success": True,
            "equation_count": len(equations),
            "edges": result["edges"],
            "frontiers": result["frontiers"],
            "hints": result["hints"],
        }

    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid equations.json: {exc}",
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Whiteboard reasoning failed: {exc}",
        )


@router.post("/action")
async def record_whiteboard_action(
    payload: WhiteboardAction,
    request: Request,
):
    """
    Store a whiteboard action in the action history log.
    """

    user_ip = (
        request.client.host
        if request.client
        else None
    )

    log_whiteboard_action(
        action=payload.action,
        element_id=payload.element_id,
        element_type=payload.element_type,
        user_ip=user_ip,
        data=payload.data,
    )

    return {
        "success": True,
    }