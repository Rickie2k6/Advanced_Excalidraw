import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter()

DATA_DIR = Path(
    "/home/student/chuynh/Chatbot/data"
)

STROKES_FILE = DATA_DIR / "strokes.json"

file_lock = asyncio.Lock()


class StrokeRecord(BaseModel):
    stroke_id: str

    created_by_ip: str | None = None

    x: float
    y: float
    width: float
    height: float

    points: list[list[float]]

    is_deleted: bool = False


class StrokeSyncRequest(BaseModel):
    strokes: list[StrokeRecord]


@router.post("/strokes/sync")
async def sync_strokes(
    payload: StrokeSyncRequest,
):
    """
    Update stroke metadata stored on the server.

    Each stroke is indexed by its Excalidraw
    element ID.
    """

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    async with file_lock:
        if STROKES_FILE.exists():
            try:
                data = json.loads(
                    STROKES_FILE.read_text(
                        encoding="utf-8"
                    )
                )
            except json.JSONDecodeError:
                data = {
                    "strokes": {}
                }
        else:
            data = {
                "strokes": {}
            }

        stored_strokes = data.setdefault(
            "strokes",
            {},
        )

        now = datetime.now(
            timezone.utc
        ).isoformat()

        for stroke in payload.strokes:
            record = stroke.model_dump()

            record["updated_at"] = now

            stored_strokes[
                stroke.stroke_id
            ] = record

        data["updated_at"] = now

        temp_file = (
            DATA_DIR /
            "strokes.json.tmp"
        )

        temp_file.write_text(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        temp_file.replace(
            STROKES_FILE
        )

    return {
        "status": "ok",
        "count": len(payload.strokes),
    }


@router.get("/strokes")
async def get_strokes():
    if not STROKES_FILE.exists():
        return {
            "strokes": {}
        }

    return json.loads(
        STROKES_FILE.read_text(
            encoding="utf-8"
        )
    )