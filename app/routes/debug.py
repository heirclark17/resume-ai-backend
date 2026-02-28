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
        "has_authorization": "authorization" in request.headers,
        "has_x_api_key": "x-api-key" in request.headers,
        "has_x_user_id": "x-user-id" in request.headers,
        "content_type": request.headers.get("content-type", ""),
        "user_agent": request.headers.get("user-agent", ""),
    }

@router.get("/env")
async def debug_env():
    """Debug endpoint to check environment configuration (no secrets exposed)"""
    return {
        "supabase_url_configured": bool(os.getenv('SUPABASE_URL', '')),
        "supabase_jwt_secret_configured": bool(os.getenv('SUPABASE_JWT_SECRET', '')),
        "supabase_anon_key_configured": bool(os.getenv('SUPABASE_ANON_KEY', '')),
        "openai_api_key_configured": bool(os.getenv('OPENAI_API_KEY', '')),
        "database_url_configured": bool(os.getenv('DATABASE_URL', '')),
    }
