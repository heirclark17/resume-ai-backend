from fastapi import Header, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from typing import Optional
import jwt
import os

# Get Supabase JWT secret from environment
SUPABASE_JWT_SECRET = os.getenv('SUPABASE_JWT_SECRET')

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

    # Validate format (should start with 'user_' or 'clerk_')
    if not (x_user_id.startswith('user_') or x_user_id.startswith('clerk_')):
        raise HTTPException(
            status_code=400,
            detail="Invalid user ID format"
        )

    return x_user_id


async def get_current_user_from_jwt(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Validate Supabase JWT and return user

    Expects Authorization header: Bearer <jwt_token>
    Creates user record if first time signing in with Supabase
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Extract token from "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header format. Expected: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = parts[1]

    if not SUPABASE_JWT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Server misconfiguration: JWT secret not set"
        )

    try:
        # Decode and validate JWT
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=['HS256'],
            options={"verify_exp": True}  # Verify token hasn't expired
        )

        # Extract user ID from JWT (Supabase puts it in 'sub' field)
        supabase_user_id = payload.get('sub')
        user_email = payload.get('email')

        if not supabase_user_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid token: missing user ID"
            )

        # Find or create user in our database
        result = await db.execute(
            select(User).where(User.supabase_id == supabase_user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            # Create new user record
            user = User(
                email=user_email,
                supabase_id=supabase_user_id,
                is_active=True
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            print(f"[Auth] Created new user from Supabase JWT: {user_email}")

        if not user.is_active:
            raise HTTPException(
                status_code=403,
                detail="User account is disabled"
            )

        return user

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except Exception as e:
        print(f"[Auth] JWT validation error: {e}")
        raise HTTPException(
            status_code=401,
            detail="Authentication failed",
            headers={"WWW-Authenticate": "Bearer"}
        )


async def get_current_user_unified(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
) -> tuple[Optional[User], str]:
    """
    Unified authentication supporting multiple methods:
    1. Supabase JWT (Authorization: Bearer <token>) - Returns User object
    2. API Key (X-API-Key) - Returns User object
    3. Session ID (X-User-ID) - Returns session ID string

    Returns: (user_object_or_None, user_id_string)

    Priority order: JWT > API Key > Session ID
    """
    # Try Supabase JWT authentication first
    if authorization:
        try:
            user = await get_current_user_from_jwt(authorization, db)
            return (user, f"supabase_{user.supabase_id}")
        except HTTPException:
            pass  # Fall through to next method

    # Try API key authentication
    if x_api_key:
        try:
            user = await get_current_user(x_api_key, db)
            return (user, f"user_{user.id}")
        except HTTPException:
            pass  # Fall through to next method

    # Fall back to session-based user ID
    if x_user_id and (x_user_id.startswith('user_') or x_user_id.startswith('clerk_')):
        return (None, x_user_id)

    # No valid authentication provided
    raise HTTPException(
        status_code=401,
        detail="Authentication required. Provide Authorization Bearer token, X-API-Key, or X-User-ID header."
    )
