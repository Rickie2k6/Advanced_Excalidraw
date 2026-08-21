from fastapi import APIRouter

from app.core.config import settings


router = APIRouter()


@router.get("/health")
def health():
    return {
        "status": "ok",

        "pipeline_version":
            settings
            .paddle_pipeline_version,

        "engine":
            settings
            .paddle_engine,

        "device":
            settings
            .paddle_device,
    }