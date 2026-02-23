from fastapi import APIRouter, Header, Request
from typing import Optional

router = APIRouter(prefix="/debug", tags=["debug"])

@router.get("/headers")
async def debug_headers(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
):
    """Debug endpoint to check what headers Railway receives"""
    return {
        "all_headers": dict(request.headers),
        "authorization_param": authorization,
        "x_api_key_param": x_api_key,
        "x_user_id_param": x_user_id,
        "has_authorization": "authorization" in request.headers,
        "has_x_api_key": "x-api-key" in request.headers,
        "has_x_user_id": "x-user-id" in request.headers,
    }
