from ipaddress import ip_address

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
)
from pydantic import BaseModel


router = APIRouter()


class ClientIPv4Report(BaseModel):
    """
    EN:
    Represent the public IPv4 address detected
    by the client's browser.

    VI:
    Đại diện cho public IPv4 được browser
    của client phát hiện.
    """

    public_ipv4: str


@router.get("/client-ip")
async def get_client_ip(
    request: Request,
):
    """
    EN:
    Return the original client IP reported by
    Cloudflare. This can be either IPv4 or IPv6.

    VI:
    Trả về IP gốc của client do Cloudflare
    cung cấp. IP này có thể là IPv4 hoặc IPv6.
    """

    client_ip = request.headers.get(
        "cf-connecting-ip"
    )

    if not client_ip:
        client_ip = (
            request.client.host
            if request.client
            else "unknown"
        )

    return {
        "public_ip": client_ip,
    }


@router.post("/client-ip/confirm")
async def confirm_client_ipv4(
    payload: ClientIPv4Report,
    request: Request,
):
    """
    EN:
    Validate an IPv4 address detected by the
    browser and return it together with the
    IP observed by Cloudflare.

    VI:
    Kiểm tra IPv4 do browser phát hiện và
    trả về cùng với IP mà Cloudflare nhìn thấy.
    """

    try:
        parsed_ip = ip_address(
            payload.public_ipv4
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail="Invalid IP address.",
        ) from error

    if parsed_ip.version != 4:
        raise HTTPException(
            status_code=400,
            detail=(
                "The submitted address "
                "is not IPv4."
            ),
        )

    cloudflare_ip = (
        request.headers.get(
            "cf-connecting-ip"
        )
    )

    print(
        "[Client IP] "
        f"IPv4={parsed_ip} "
        f"Cloudflare={cloudflare_ip}"
    )

    return {
        "public_ipv4": str(parsed_ip),
        "cloudflare_ip": cloudflare_ip,
    }