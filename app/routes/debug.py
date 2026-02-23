from fastapi import APIRouter, Header, Request
from typing import Optional
import os

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

@router.get("/env")
async def debug_env():
    """Debug endpoint to check environment configuration"""
    supabase_url = os.getenv('SUPABASE_URL', '')
    supabase_jwt_secret = os.getenv('SUPABASE_JWT_SECRET', '')

    return {
        "supabase_url_configured": bool(supabase_url),
        "supabase_url_length": len(supabase_url),
        "supabase_url_starts_with_https": supabase_url.startswith('https://'),
        "supabase_jwt_secret_configured": bool(supabase_jwt_secret),
        "jwks_url": f"{supabase_url}/auth/v1/jwks" if supabase_url else "NOT_CONFIGURED",
    }
