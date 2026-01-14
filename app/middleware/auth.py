from fastapi import Header, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from typing import Optional

async def get_current_user(
    x_api_key: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Dependency to get current authenticated user from API key

    Usage:
        @router.get("/endpoint")
        async def protected_endpoint(current_user: User = Depends(get_current_user)):
            # Access current_user.id, current_user.email, etc.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    # Get all active users (we need to check hashed keys)
    result = await db.execute(select(User))
    users = result.scalars().all()

    # Find user by verifying API key against hashed keys
    user = None
    for potential_user in users:
        # Try hashed comparison first (new format)
        if User.verify_api_key(x_api_key, potential_user.api_key):
            user = potential_user
            break
        # Fallback: Check if it's a plaintext key (migration compatibility)
        elif potential_user.api_key == x_api_key:
            user = potential_user
            # Auto-migrate: rehash the key
            potential_user.api_key = User.hash_api_key(x_api_key)
            db.add(potential_user)
            await db.commit()
            break

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="User account is disabled"
        )

    return user


async def get_current_user_optional(
    x_api_key: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Optional authentication - returns None if no API key provided
    Use this for endpoints that work both with and without auth
    """
    if not x_api_key:
        return None

    try:
        return await get_current_user(x_api_key, db)
    except HTTPException:
        return None


async def get_user_id(
    x_user_id: Optional[str] = Header(None),
) -> str:
    """
    Get user ID from header (required for data isolation)

    This provides session-based user isolation without full authentication.
    The frontend generates a unique user ID stored in localStorage.

    Usage:
        @router.get("/endpoint")
        async def endpoint(user_id: str = Depends(get_user_id)):
            # Filter data by user_id
    """
    if not x_user_id:
        raise HTTPException(
            status_code=401,
            detail="User ID required. Please refresh the page."
        )

    # Validate format (should start with 'user_')
    if not x_user_id.startswith('user_'):
        raise HTTPException(
            status_code=400,
            detail="Invalid user ID format"
        )

    return x_user_id
