from functools import lru_cache

from paddleocr import PaddleOCRVL

from app.core.config import settings


@lru_cache(maxsize=1)
def get_pipeline():
    print(
        "Loading PaddleOCR-VL pipeline..."
    )

    kwargs = {
        "pipeline_version":
            settings.paddle_pipeline_version,

        "engine":
            settings.paddle_engine,
    }

    if settings.paddle_device:
        kwargs["device"] = (
            settings.paddle_device
        )

    pipeline = PaddleOCRVL(
        **kwargs
    )

    print(
        "PaddleOCR-VL pipeline loaded."
    )

    return pipeline