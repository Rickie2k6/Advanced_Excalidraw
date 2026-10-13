from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Form,
)

from pathlib import Path

from app.core.paths import (
    WHITEBOARD_IMAGES_DIR,
)


router = APIRouter(
    prefix="/whiteboard",
    tags=["whiteboard-images"],
)


@router.post("/images")
async def upload_whiteboard_image(
    image: UploadFile = File(...),
    file_id: str = Form(...),
    element_id: str = Form(...),
    mime_type: str = Form(...),
    x: float = Form(...),
    y: float = Form(...),
    width: float = Form(...),
    height: float = Form(...),
):
    # ============================================================
    # 1. DETERMINE FILE EXTENSION
    # ============================================================

    extension = Path(
        image.filename or ""
    ).suffix or ".png"


    # ============================================================
    # 2. BUILD IMAGE PATH
    # ============================================================

    image_path = (
        WHITEBOARD_IMAGES_DIR /
        f"{file_id}{extension}"
    )


    # ============================================================
    # 3. READ IMAGE
    # ============================================================

    image_bytes = await image.read()


    # ============================================================
    # 4. SAVE IMAGE
    # ============================================================

    image_path.write_bytes(
        image_bytes
    )


    # ============================================================
    # 5. RESPONSE
    # ============================================================

    return {
        "success": True,

        "file_id": file_id,
        "element_id": element_id,

        "mime_type": mime_type,

        "path": str(
            image_path
        ),

        "bbox": {
            "x": x,
            "y": y,
            "width": width,
            "height": height,
        },

        "size_bytes":
            len(image_bytes),
    }