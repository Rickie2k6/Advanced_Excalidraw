import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import ( 
    APIRouter,
    File,
    HTTPException,
    UploadFile,
)
from pydantic import BaseModel

from app.services.stroke_grouper import (
    group_freedraw_strokes,
)

from starlette.concurrency import (
    run_in_threadpool,
)

from app.services.equation_ocr import (
    recognize_equation,
)

router = APIRouter()

DATA_DIR = Path(
    "/home/student/chuynh/Chatbot/data"
)

STROKES_FILE = DATA_DIR / "strokes.json"
EQUATIONS_FILE = DATA_DIR / "equations.json"

file_lock = asyncio.Lock()


# ============================================================
# MODELS
# ============================================================


class BoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class EquationRecord(BaseModel):
    equation: str | None = None

    stroke_ids: list[str]

    bbox: BoundingBox

    confidence: float | None = None


class EquationSyncRequest(BaseModel):
    equations: list[EquationRecord]


# ============================================================
# HELPERS
# ============================================================


def build_equation_id(
    stroke_ids: list[str],
) -> str:
    """
    Generate a stable equation ID based on
    the strokes composing the equation.
    """

    normalized = "|".join(
        sorted(stroke_ids)
    )

    digest = hashlib.sha1(
        normalized.encode("utf-8")
    ).hexdigest()[:12]

    return f"eq_{digest}"


def load_strokes_file() -> dict:
    """
    Load the complete strokes.json structure.
    """

    if not STROKES_FILE.exists():
        return {
            "strokes": {}
        }

    try:
        return json.loads(
            STROKES_FILE.read_text(
                encoding="utf-8"
            )
        )

    except (
        json.JSONDecodeError,
        OSError,
    ):
        return {
            "strokes": {}
        }


def load_equations_file() -> dict:
    """
    Load equations.json safely.
    """

    if not EQUATIONS_FILE.exists():
        return {
            "equations": {}
        }

    try:
        return json.loads(
            EQUATIONS_FILE.read_text(
                encoding="utf-8"
            )
        )

    except (
        json.JSONDecodeError,
        OSError,
    ):
        return {
            "equations": {}
        }


def save_equations_file(
    data: dict,
) -> None:
    """
    Write equations.json atomically.
    """

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_file = (
        DATA_DIR /
        "equations.json.tmp"
    )

    temporary_file.write_text(
        json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    temporary_file.replace(
        EQUATIONS_FILE
    )


def get_contributors(
    stroke_ids: list[str],
    strokes: dict,
) -> list[str]:
    """
    Resolve contributors from strokes.json.

    Prefer contributor_id.
    Fall back to IP for legacy strokes.
    """

    contributors = set()

    for stroke_id in stroke_ids:
        stroke = strokes.get(
            stroke_id
        )

        if not stroke:
            continue

        contributor_id = stroke.get(
            "contributor_id"
        )

        created_by_ip = stroke.get(
            "created_by_ip"
        )

        contributor = (
            contributor_id
            or created_by_ip
        )

        if contributor:
            contributors.add(
                contributor
            )

    return sorted(
        contributors
    )


# ============================================================
# GROUP STROKES INTO EQUATION BLOCKS
# ============================================================


@router.post("/equations/group")
async def group_equations():
    """
    Read strokes.json, group nearby freedraw
    strokes into candidate equation blocks,
    and write them to equations.json.

    OCR is NOT performed here yet.
    """

    async with file_lock:

        strokes_data = (
            load_strokes_file()
        )

        groups = (
            group_freedraw_strokes(
                strokes_data
            )
        )

        old_data = (
            load_equations_file()
        )

        old_equations = (
            old_data.get(
                "equations",
                {},
            )
        )

        now = datetime.now(
            timezone.utc
        ).isoformat()

        equations = {}

        for group in groups:

            stroke_ids = group[
                "stroke_ids"
            ]

            equation_id = (
                build_equation_id(
                    stroke_ids
                )
            )

            previous = (
                old_equations.get(
                    equation_id,
                    {},
                )
            )

            equations[
                equation_id
            ] = {
                "equation_id":
                    equation_id,

                # Preserve OCR result if the
                # exact same stroke group
                # already existed.
                "equation":
                    previous.get(
                        "equation"
                    ),

                "stroke_ids":
                    stroke_ids,

                "bbox":
                    group["bbox"],

                "contributors":
                    group.get(
                        "contributors",
                        [],
                    ),

                "confidence":
                    previous.get(
                        "confidence"
                    ),

                "updated_at":
                    now,
            }

        data = {
            "updated_at":
                now,

            "equations":
                equations,
        }

        save_equations_file(
            data
        )

    return {
        "status": "ok",
        "count": len(
            equations
        ),
        "equations": equations,
    }

# ============================================================
# OCR ONE EQUATION IMAGE
# ============================================================


@router.post(
    "/equations/{equation_id}/ocr"
)
async def ocr_equation(
    equation_id: str,
    image: UploadFile = File(...),
):
    """
    Receive one PNG containing one equation,
    recognize it with PaddleOCR-VL, and update
    equations.json.
    """

    # --------------------------------------------------------
    # 1. Find equation metadata.
    # --------------------------------------------------------

    async with file_lock:

        data = (
            load_equations_file()
        )

        equations = (
            data.get(
                "equations",
                {},
            )
        )

        equation_record = (
            equations.get(
                equation_id
            )
        )

        if not equation_record:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Equation "
                    f"{equation_id} "
                    "was not found."
                ),
            )

        bbox = (
            equation_record.get(
                "bbox"
            )
        )

        if not bbox:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Equation does not "
                    "contain bbox metadata."
                ),
            )


    # --------------------------------------------------------
    # 2. Read PNG bytes.
    # --------------------------------------------------------

    image_bytes = (
        await image.read()
    )

    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail=(
                "Uploaded equation image "
                "is empty."
            ),
        )


    # --------------------------------------------------------
    # 3. Run Paddle OCR.
    # --------------------------------------------------------

    try:
        result = (
            await run_in_threadpool(
                recognize_equation,
                image_bytes,
                bbox,
            )
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error

    except RuntimeError as error:
        raise HTTPException(
            status_code=500,
            detail=str(error),
        ) from error


    recognized_equation = (
        result.get(
            "equation"
        )
    )

    confidence = (
        result.get(
            "confidence"
        )
    )

    if not recognized_equation:
        raise HTTPException(
            status_code=422,
            detail=(
                "PaddleOCR did not "
                "recognize an equation."
            ),
        )


    # --------------------------------------------------------
    # 4. Update equations.json.
    # --------------------------------------------------------

    async with file_lock:

        data = (
            load_equations_file()
        )

        equations = (
            data.get(
                "equations",
                {},
            )
        )

        equation_record = (
            equations.get(
                equation_id
            )
        )

        if not equation_record:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Equation disappeared "
                    "before OCR completed."
                ),
            )

        now = datetime.now(
            timezone.utc
        ).isoformat()

        equation_record[
            "equation"
        ] = recognized_equation

        equation_record[
            "confidence"
        ] = confidence

        equation_record[
            "updated_at"
        ] = now

        data[
            "updated_at"
        ] = now

        save_equations_file(
            data
        )


    return {
        "status": "ok",

        "equation_id":
            equation_id,

        "equation":
            recognized_equation,

        "confidence":
            confidence,
    }

# ============================================================
# SAVE OCR / RECOGNIZED EQUATIONS
# ============================================================


@router.post("/equations/sync")
async def sync_equations(
    payload: EquationSyncRequest,
):
    """
    Save OCR results for equation groups.

    Contributor IPs are always derived from
    strokes.json.
    """

    async with file_lock:

        strokes_data = (
            load_strokes_file()
        )

        strokes = (
            strokes_data.get(
                "strokes",
                {},
            )
        )

        data = (
            load_equations_file()
        )

        equations = (
            data.setdefault(
                "equations",
                {},
            )
        )

        now = datetime.now(
            timezone.utc
        ).isoformat()

        for item in payload.equations:

            equation_id = (
                build_equation_id(
                    item.stroke_ids
                )
            )

            contributors = (
                get_contributors(
                    item.stroke_ids,
                    strokes,
                )
            )

            equations[
                equation_id
            ] = {
                "equation_id":
                    equation_id,

                "equation":
                    item.equation,

                "stroke_ids":
                    item.stroke_ids,

                "bbox":
                    item.bbox.model_dump(),

                "contributors":
                    contributors,

                "confidence":
                    item.confidence,

                "updated_at":
                    now,
            }

        data["updated_at"] = (
            now
        )

        save_equations_file(
            data
        )

    return {
        "status": "ok",
        "count": len(
            payload.equations
        ),
    }


# ============================================================
# GET EQUATIONS
# ============================================================


@router.get("/equations")
async def get_equations():
    return load_equations_file()