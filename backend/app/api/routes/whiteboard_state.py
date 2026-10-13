import json

from datetime import (
    datetime,
    timezone,
)

from fastapi import (
    APIRouter,
    Body,
)

from app.core.paths import (
    WHITEBOARD_ELEMENTS_FILE,
    WHITEBOARD_APP_STATE_FILE,
)


router = APIRouter(
    prefix="/whiteboard",
    tags=["whiteboard-state"],
)


@router.post("/state")
async def save_whiteboard_state(
    payload: dict = Body(...),
):
    elements = payload.get(
        "elements",
        [],
    )

    app_state = payload.get(
        "app_state",
        {},
    )

    updated_at = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )


    # ============================================================
    # 1. SAVE ELEMENTS
    # ============================================================

    elements_data = {
        "updated_at":
            updated_at,

        "count":
            len(elements),

        "elements":
            elements,
    }

    elements_temp_path = (
        WHITEBOARD_ELEMENTS_FILE
        .with_suffix(".tmp")
    )

    with open(
        elements_temp_path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            elements_data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    elements_temp_path.replace(
        WHITEBOARD_ELEMENTS_FILE
    )


    # ============================================================
    # 2. SAVE APP STATE
    # ============================================================

    app_state_data = {
        "updated_at":
            updated_at,

        "app_state":
            app_state,
    }

    app_state_temp_path = (
        WHITEBOARD_APP_STATE_FILE
        .with_suffix(".tmp")
    )

    with open(
        app_state_temp_path,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            app_state_data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    app_state_temp_path.replace(
        WHITEBOARD_APP_STATE_FILE
    )


    # ============================================================
    # 3. RESPONSE
    # ============================================================

    return {
        "success": True,

        "element_count":
            len(elements),

        "elements_path":
            str(
                WHITEBOARD_ELEMENTS_FILE
            ),

        "app_state_path":
            str(
                WHITEBOARD_APP_STATE_FILE
            ),
    }


@router.get("/state")
async def get_whiteboard_state():

    elements = []
    app_state = {}

    updated_at = None


    # ============================================================
    # 1. LOAD ELEMENTS
    # ============================================================

    if WHITEBOARD_ELEMENTS_FILE.exists():
        with open(
            WHITEBOARD_ELEMENTS_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            elements_data = (
                json.load(file)
            )

        elements = (
            elements_data.get(
                "elements",
                [],
            )
        )

        updated_at = (
            elements_data.get(
                "updated_at"
            )
        )


    # ============================================================
    # 2. LOAD APP STATE
    # ============================================================

    if WHITEBOARD_APP_STATE_FILE.exists():
        with open(
            WHITEBOARD_APP_STATE_FILE,
            "r",
            encoding="utf-8",
        ) as file:
            app_state_data = (
                json.load(file)
            )

        app_state = (
            app_state_data.get(
                "app_state",
                {},
            )
        )

        if updated_at is None:
            updated_at = (
                app_state_data.get(
                    "updated_at"
                )
            )


    # ============================================================
    # 3. RETURN COMBINED CURRENT STATE
    # ============================================================

    return {
        "updated_at":
            updated_at,

        "elements":
            elements,

        "app_state":
            app_state,
    }