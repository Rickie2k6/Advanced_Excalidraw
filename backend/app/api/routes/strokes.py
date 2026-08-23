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

STROKES_FILE = (
    DATA_DIR /
    "strokes.json"
)

EQUATIONS_FILE = (
    DATA_DIR /
    "equations.json"
)

file_lock = asyncio.Lock()


class StrokeRecord(BaseModel):
    stroke_id: str

    contributor_id: str | None = None
    created_by_ip: str | None = None

    x: float
    y: float

    width: float
    height: float

    points: list[list[float]]

    is_deleted: bool = False


class StrokeSyncRequest(BaseModel):
    strokes: list[StrokeRecord]


def write_json_atomic(
    path: Path,
    data: dict,
):
    temp_file = path.with_suffix(
        path.suffix + ".tmp"
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
        path
    )


def prune_equations(
    active_stroke_ids: set[str],
    now: str,
):
    """
    Remove equations whose strokes no longer
    exist on the current whiteboard.
    """

    if not EQUATIONS_FILE.exists():
        return

    try:
        data = json.loads(
            EQUATIONS_FILE.read_text(
                encoding="utf-8"
            )
        )
    except (
        json.JSONDecodeError,
        OSError,
    ):
        data = {
            "equations": {}
        }

    equations = data.get(
        "equations",
        {},
    )

    valid_equations = {}

    for (
        equation_id,
        equation,
    ) in equations.items():
        stroke_ids = equation.get(
            "stroke_ids",
            [],
        )

        if not stroke_ids:
            continue

        equation_stroke_ids = set(
            stroke_ids
        )

        # Keep an equation only if ALL of its
        # strokes still exist on the board.
        if equation_stroke_ids.issubset(
            active_stroke_ids
        ):
            valid_equations[
                equation_id
            ] = equation

    equations_data = {
        "updated_at": now,
        "equations":
            valid_equations,
    }

    write_json_atomic(
        EQUATIONS_FILE,
        equations_data,
    )


@router.post("/strokes/sync")
async def sync_strokes(
    payload: StrokeSyncRequest,
):
    """
    Synchronize the COMPLETE current
    whiteboard stroke snapshot.

    This endpoint does NOT append strokes.
    The payload represents the current
    whiteboard state.
    """

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    async with file_lock:
        now = datetime.now(
            timezone.utc
        ).isoformat()

        # ==========================================
        # 1. Build current stroke snapshot
        # ==========================================

        current_strokes = {}

        active_stroke_ids: set[str] = set()

        for stroke in payload.strokes:
            record = stroke.model_dump()

            record["updated_at"] = now

            current_strokes[
                stroke.stroke_id
            ] = record

            if not stroke.is_deleted:
                active_stroke_ids.add(
                    stroke.stroke_id
                )

        # ==========================================
        # 2. Replace strokes.json completely
        # ==========================================

        strokes_data = {
            "updated_at": now,
            "strokes":
                current_strokes,
        }

        write_json_atomic(
            STROKES_FILE,
            strokes_data,
        )

        # ==========================================
        # 3. Remove stale equations
        # ==========================================

        prune_equations(
            active_stroke_ids,
            now,
        )

    return {
        "status":
            "ok",

        "count":
            len(payload.strokes),

        "active_count":
            len(active_stroke_ids),
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