from fastapi import APIRouter

from app.core.state_store import (
    get_history,
)


router = APIRouter()


@router.get("/history")
def history():
    runs = get_history()

    return {
        "count": len(runs),
        "runs": runs,
    }