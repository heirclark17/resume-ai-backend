"""
Test endpoints for Supabase JWT authentication
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.user import User
from app.middleware.auth import get_current_user_from_jwt, get_current_user_unified

router = APIRouter()


@router.get("/test/jwt")
async def test_jwt_auth(
    current_user: User = Depends(get_current_user_from_jwt),
    db: AsyncSession = Depends(get_db)
):
    """
    Test Supabase JWT authentication

    Send request with: Authorization: Bearer <your_jwt_token>

    Returns user info if JWT is valid
    """
    return {
        "success": True,
        "message": "JWT authentication successful!",
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "supabase_id": current_user.supabase_id,
            "is_active": current_user.is_active,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None
        },
        "auth_method": "supabase_jwt"
    }


@router.get("/test/unified")
async def test_unified_auth(
    auth_result: tuple = Depends(get_current_user_unified),
    db: AsyncSession = Depends(get_db)
):
    """
    Test unified authentication (supports JWT, API Key, or Session ID)

    Send one of:
    - Authorization: Bearer <jwt_token>
    - X-API-Key: <api_key>
    - X-User-ID: <user_id>

    Returns authentication info
    """
    user, user_id = auth_result

    if user:
        # Authenticated via JWT or API Key
        return {
            "success": True,
            "message": "Authenticated via user account",
            "user": {
                "id": user.id,
                "email": user.email,
                "supabase_id": user.supabase_id,
                "username": user.username,
                "is_active": user.is_active
            },
            "session_id": user_id,
            "auth_method": "jwt" if user.supabase_id else "api_key"
        }
    else:
        # Authenticated via session ID only
        return {
            "success": True,
            "message": "Authenticated via session ID",
            "session_id": user_id,
            "auth_method": "session",
            "note": "Consider signing in for full account features"
        }


@router.get("/test/whoami")
async def whoami(
    auth_result: tuple = Depends(get_current_user_unified)
):
    """
    Quick test - Who am I?

    Returns minimal auth info
    """
    user, user_id = auth_result

    if user:
        return {
            "authenticated": True,
            "email": user.email,
            "user_id": user_id,
            "method": "jwt" if user.supabase_id else "api_key"
        }
    else:
        return {
            "authenticated": True,
            "email": None,
            "user_id": user_id,
            "method": "session"
        }
