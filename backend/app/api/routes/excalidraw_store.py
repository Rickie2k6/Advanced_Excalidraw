import httpx

from fastapi import (
    APIRouter,
    Request,
)

from fastapi.responses import Response


router = APIRouter()


EXCALIDRAW_STORE_URL = (
    "https://json.excalidraw.com/api/v2"
)


@router.post("/excalidraw-store/post/")
async def proxy_excalidraw_post(
    request: Request,
):
    body = await request.body()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{EXCALIDRAW_STORE_URL}/post/",
            content=body,
            headers={
                "Content-Type":
                    "application/octet-stream",
            },
        )

    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type=response.headers.get(
            "content-type",
            "application/json",
        ),
    )


@router.get("/excalidraw-store/{share_id}")
async def proxy_excalidraw_get(
    share_id: str,
):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{EXCALIDRAW_STORE_URL}/{share_id}"
        )

    return Response(
        content=response.content,
        status_code=response.status_code,
        media_type="application/octet-stream",
    )