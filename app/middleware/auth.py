from fastapi import Header, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from typing import Optional
import jwt
import os
import httpx
from functools import lru_cache

# Get Supabase configuration from environment
SUPABASE_JWT_SECRET = os.getenv('SUPABASE_JWT_SECRET')
SUPABASE_URL = os.getenv('SUPABASE_URL', '')

# Cache for Supabase public key (ES256)
_supabase_public_key_cache = None


async def get_supabase_public_key():
    """
    Fetch Supabase public key for ES256 JWT verification
    Caches the key to avoid repeated requests
    """
    global _supabase_public_key_cache

    if _supabase_public_key_cache:
        print("[Auth] Using cached Supabase public key")
        return _supabase_public_key_cache

    print(f"[Auth] SUPABASE_URL configured: {bool(SUPABASE_URL)} (length: {len(SUPABASE_URL)})")

    try:
        # Supabase JWKS endpoint (well-known standard location)
        jwks_url = f"{SUPABASE_URL}/auth/v1/jwks"
        print(f"[Auth] Fetching JWKS from: {jwks_url}")

        async with httpx.AsyncClient() as client:
            response = await client.get(jwks_url, timeout=5.0)
            response.raise_for_status()
            jwks = response.json()
            print(f"[Auth] JWKS response received, keys count: {len(jwks.get('keys', []))}")

        # Extract the first key (Supabase typically has one ES256 key)
        if 'keys' in jwks and len(jwks['keys']) > 0:
            key_data = jwks['keys'][0]

            # Convert JWKS to PEM format for PyJWT
            from jwt.algorithms import RSAAlgorithm, ECAlgorithm

            # Check key type (RS256 or ES256)
            if key_data.get('kty') == 'RSA':
                public_key = RSAAlgorithm.from_jwk(key_data)
            elif key_data.get('kty') == 'EC':
                public_key = ECAlgorithm.from_jwk(key_data)
            else:
                raise ValueError(f"Unsupported key type: {key_data.get('kty')}")

            _supabase_public_key_cache = public_key
            print(f"[Auth] Cached Supabase public key (type: {key_data.get('kty')})")
            return public_key
        else:
            raise ValueError("No keys found in JWKS")

    except Exception as e:
        print(f"[Auth] Failed to fetch Supabase public key: {e}")
        # Fall back to JWT secret if public key fetch fails
        return SUPABASE_JWT_SECRET


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

    # Validate format (should start with 'user_', 'clerk_', or 'supa_')
    if not (x_user_id.startswith('user_') or x_user_id.startswith('clerk_') or x_user_id.startswith('supa_')):
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

    try:
        # First, decode header to check algorithm (don't verify yet)
        unverified_header = jwt.get_unverified_header(token)
        token_algorithm = unverified_header.get('alg', 'HS256')

        print(f"[Auth] JWT algorithm: {token_algorithm}")

        # Get appropriate key for verification
        if token_algorithm == 'ES256':
            # ES256 tokens - use public key from JWKS
            verification_key = await get_supabase_public_key()
            algorithms = ['ES256', 'RS256']  # Support both EC and RSA
            print("[Auth] Using public key verification (ES256/RS256)")
        else:
            # HS256 tokens - use shared secret
            if not SUPABASE_JWT_SECRET:
                raise HTTPException(
                    status_code=500,
                    detail="Server misconfiguration: JWT secret not set"
                )
            verification_key = SUPABASE_JWT_SECRET
            algorithms = ['HS256']
            print("[Auth] Using shared secret verification (HS256)")

        # Decode and validate JWT with appropriate key and algorithm
        payload = jwt.decode(
            token,
            verification_key,
            algorithms=algorithms,
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
    print(f"[Auth] Unified auth called with: auth={bool(authorization)}, api_key={bool(x_api_key)}, user_id={bool(x_user_id)}")

    # Try Supabase JWT authentication first
    if authorization:
        try:
            print(f"[Auth] Attempting JWT auth with token: {authorization[:30]}...")
            user = await get_current_user_from_jwt(authorization, db)
            print(f"[Auth] JWT auth succeeded for user: {user.email}")
            return (user, f"supabase_{user.supabase_id}")
        except HTTPException as e:
            print(f"[Auth] JWT auth failed: {e.detail}")
            pass  # Fall through to next method
        except Exception as e:
            print(f"[Auth] JWT auth error: {type(e).__name__}: {str(e)}")
            pass  # Fall through to next method

    # Try API key authentication
    if x_api_key:
        try:
            user = await get_current_user(x_api_key, db)
            return (user, f"user_{user.id}")
        except HTTPException:
            pass  # Fall through to next method

    # Fall back to session-based user ID
    if x_user_id and (x_user_id.startswith('user_') or x_user_id.startswith('clerk_') or x_user_id.startswith('supa_')):
        return (None, x_user_id)

    # No valid authentication provided
    raise HTTPException(
        status_code=401,
        detail="Authentication required. Provide Authorization Bearer token, X-API-Key, or X-User-ID header."
    )
