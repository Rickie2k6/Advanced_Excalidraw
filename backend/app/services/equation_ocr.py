from __future__ import annotations

from io import BytesIO
from typing import Any

from PIL import (
    Image,
    UnidentifiedImageError,
)

from app.services.paddle.analyzer import (
    analyze_equation_images,
)


def _image_from_bytes(
    image_bytes: bytes,
) -> Image.Image:
    """
    Convert uploaded PNG/JPEG bytes into
    a PIL RGB image.
    """

    if not image_bytes:
        raise ValueError(
            "Equation image is empty."
        )

    try:
        with Image.open(
            BytesIO(image_bytes)
        ) as image:

            # Make a detached copy because
            # BytesIO/Image.open will be closed
            # after leaving this block.
            return (
                image
                .convert("RGB")
                .copy()
            )

    except (
        UnidentifiedImageError,
        OSError,
    ) as error:
        raise ValueError(
            "Invalid equation image."
        ) from error


def _bbox_to_list(
    bbox: dict[str, Any],
) -> list[float]:
    """
    Convert equation bbox:

    {
        "x": ...,
        "y": ...,
        "width": ...,
        "height": ...
    }

    into a numeric list passed to the
    existing Paddle analyzer metadata.
    """

    try:
        return [
            float(bbox["x"]),
            float(bbox["y"]),
            float(bbox["width"]),
            float(bbox["height"]),
        ]

    except (
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        raise ValueError(
            "Invalid equation bounding box."
        ) from error


def recognize_equation(
    image_bytes: bytes,
    bbox: dict[str, Any],
) -> dict[str, Any]:
    """
    Recognize ONE equation image using the
    existing PaddleOCR-VL pipeline.

    Important:
    This function does NOT create or load
    another Paddle model. It reuses:

        analyze_equation_images()

    from app.services.paddle.analyzer.
    """

    image = _image_from_bytes(
        image_bytes
    )

    bbox_list = _bbox_to_list(
        bbox
    )

    # analyze_equation_images() casts metadata
    # "id" to int, so use a local numeric ID.
    #
    # The real equation_id (eq_xxxxx) remains
    # managed by equations.py.
    boxes_meta = [
        {
            "id": 1,
            "bbox": bbox_list,
        }
    ]

    analysis = (
        analyze_equation_images(
            [image],
            boxes_meta,
        )
    )

    boxes = analysis.get(
        "boxes",
        []
    )

    if not boxes:
        raise RuntimeError(
            "PaddleOCR returned no "
            "recognized equation."
        )

    result = boxes[0]

    equation = result.get(
        "equation"
    )

    if equation is None:
        raise RuntimeError(
            "PaddleOCR result does not "
            "contain an equation."
        )

    return {
        "equation": equation,

        # Current analyze_equation_images()
        # does not expose a confidence score.
        "confidence": None,
    }