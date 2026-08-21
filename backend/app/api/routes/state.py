from fastapi import APIRouter

from app.core.state_store import (
    get_current_state,
)


router = APIRouter()


@router.get("/state")
def state():
    return get_current_state()