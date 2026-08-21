import json

from fastapi import (
    APIRouter,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from starlette.concurrency import (
    run_in_threadpool,
)

from app.core.state_store import (
    update_analysis,
)

from app.schemas.analysis import (
    AnalysisResult,
)

from app.services.paddle.analyzer import (
    analyze_equation_images,
    analyze_whiteboard,
)

from app.utils.images import (
    upload_to_image,
)


router = APIRouter()


@router.post(
    "/analyze",
    response_model=AnalysisResult,
)
async def analyze(
    whiteboard: UploadFile = File(...),
):
    """
    EN:
    Analyze one complete whiteboard image using
    the original PaddleOCR layout-detection flow.

    VI:
    Phân tích toàn bộ một ảnh whiteboard bằng
    flow PaddleOCR layout detection ban đầu.
    """
    image = await upload_to_image(
        whiteboard
    )

    analysis = await run_in_threadpool(
        analyze_whiteboard,
        image,
    )

    update_analysis(
        analysis
    )

    return analysis


@router.post(
    "/analyze-equations",
)
async def analyze_equations(
    boxes_json: str = Form(...),

    equation_images:
        list[UploadFile] = File(...),
):
    """
    EN:
    Receive equation crops and bounding-box metadata
    from the Excalidraw chatbot integration, then
    recognize each equation using PaddleOCR-VL.

    VI:
    Nhận các ảnh crop equation và metadata bounding box
    từ chatbot tích hợp với Excalidraw, sau đó sử dụng
    PaddleOCR-VL để nhận dạng từng phương trình.
    """
    try:
        boxes_meta = json.loads(
            boxes_json
        )
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail=(
                "boxes_json is not "
                "valid JSON."
            ),
        )

    if not isinstance(
        boxes_meta,
        list,
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "boxes_json must "
                "contain a list."
            ),
        )

    if not equation_images:
        raise HTTPException(
            status_code=400,
            detail=(
                "At least one equation "
                "image is required."
            ),
        )

    if len(boxes_meta) != len(
        equation_images
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Number of equation boxes "
                "does not match number of "
                "equation images."
            ),
        )

    images = []

    for upload in equation_images:
        image = await upload_to_image(
            upload
        )

        images.append(
            image
        )

    try:
        analysis = (
            await run_in_threadpool(
                analyze_equation_images,
                images,
                boxes_meta,
            )
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    update_analysis(
        analysis
    )

    return analysis