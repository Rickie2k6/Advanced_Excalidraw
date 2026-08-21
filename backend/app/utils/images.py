from io import BytesIO

from fastapi import (
    HTTPException,
    UploadFile,
)

from PIL import (
    Image,
    UnidentifiedImageError,
)


async def upload_to_image(
    upload: UploadFile,
) -> Image.Image:
    data = await upload.read()

    if not data:
        raise HTTPException(
            status_code=400,
            detail=(
                "The uploaded "
                "whiteboard image is empty."
            ),
        )

    try:
        image = Image.open(
            BytesIO(data)
        )

        image.load()

        return image.convert(
            "RGB"
        )

    except (
        UnidentifiedImageError,
        OSError,
    ) as error:
        raise HTTPException(
            status_code=400,
            detail=(
                "The uploaded file "
                "is not a valid image."
            ),
        ) from error