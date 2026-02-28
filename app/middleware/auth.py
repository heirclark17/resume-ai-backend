from fastapi import Header, HTTPException, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from typing import Optional
import jwt
import os
import time
import httpx
from functools import lru_cache
from app.utils.logger import logger

# Get Supabase configuration from environment
SUPABASE_JWT_SECRET = os.getenv('SUPABASE_JWT_SECRET')
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY', '')

# Cache for Supabase public key (ES256) with TTL
_supabase_public_key_cache = None
_supabase_public_key_cached_at = 0.0
_JWKS_CACHE_TTL_SECONDS = 6 * 3600  # 6 hours


async def get_supabase_public_key():
    """
    Fetch Supabase public key for ES256 JWT verification
    Caches the key with a 6-hour TTL to pick up key rotations
    """
    global _supabase_public_key_cache, _supabase_public_key_cached_at

    now = time.monotonic()
    if _supabase_public_key_cache and (now - _supabase_public_key_cached_at) < _JWKS_CACHE_TTL_SECONDS:
        logger.debug("[Auth] Using cached Supabase public key")
        return _supabase_public_key_cache

    logger.info(f"[Auth] SUPABASE_URL configured: {bool(SUPABASE_URL)} (length: {len(SUPABASE_URL)})")

    try:
        # Supabase JWKS endpoint (public .well-known endpoint - no auth required)
        jwks_url = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
        logger.info(f"[Auth] Fetching JWKS from: {jwks_url}")

        async with httpx.AsyncClient() as client:
            response = await client.get(jwks_url, timeout=5.0)
            response.raise_for_status()
            jwks = response.json()
            logger.info(f"[Auth] JWKS response received, keys count: {len(jwks.get('keys', []))}")

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
            _supabase_public_key_cached_at = time.monotonic()
            logger.info(f"[Auth] Cached Supabase public key (type: {key_data.get('kty')}, TTL: {_JWKS_CACHE_TTL_SECONDS}s)")
            return public_key
        else:
            raise ValueError("No keys found in JWKS")

    except Exception as e:
        logger.error(f"[Auth] Failed to fetch Supabase public key: {e}", exc_info=True)
        # Cannot fall back for ES256 tokens - they require public key
        raise Exception(f"Cannot verify ES256 token: JWKS fetch failed: {e}")


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

    # O(1) lookup: query by key prefix, then verify with bcrypt
    prefix = x_api_key[:8]
    result = await db.execute(
        select(User).where(User.api_key_prefix == prefix)
    )
    candidates = result.scalars().all()

    user = None
    for candidate in candidates:
        if User.verify_api_key(x_api_key, candidate.api_key):
            user = candidate
            break

    # Fallback for keys without prefix (migration): try plaintext match
    if not user:
        result = await db.execute(
            select(User).where(User.api_key == x_api_key)
        )
        legacy_user = result.scalar_one_or_none()
        if legacy_user:
            user = legacy_user
            # Auto-migrate: rehash the key and store prefix
            legacy_user.api_key = User.hash_api_key(x_api_key)
            legacy_user.api_key_prefix = User.get_key_prefix(x_api_key)
            db.add(legacy_user)
            await db.commit()

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

    # Validate format (should start with 'user_' or 'supa_')
    if not (x_user_id.startswith('user_') or x_user_id.startswith('supa_')):
        raise HTTPException(
            status_code=400,
            detail="Invalid user ID format"
        )

    return x_user_id


def check_ownership(record_user_id: str, request_user_id: str) -> bool:
    """
    Check if a record belongs to the requesting user.
    Handles migration from anonymous user_ IDs to supa_ IDs:
    if the record has a user_ ID and the request comes from supa_,
    we treat it as a match (same person who signed up).
    Also handles raw UUID records (no prefix) matching supa_ users.
    """
    if record_user_id == request_user_id:
        return True
    # Allow supa_ users to claim their old user_ records
    if record_user_id and record_user_id.startswith('user_') and request_user_id.startswith('supa_'):
        return True
    # Allow supa_ users to claim records stored with raw UUID (no prefix)
    if record_user_id and request_user_id.startswith('supa_') and request_user_id == f"supa_{record_user_id}":
        return True
    return False


def ownership_filter(column, user_id: str):
    """
    Build a SQLAlchemy filter for ownership that handles user_ → supa_ migration.
    For supa_ users, matches the supa_ ID, any user_ IDs, and raw UUID records.
    Use in .where() clauses for list queries.
    """
    from sqlalchemy import or_
    if user_id.startswith('supa_'):
        raw_uuid = user_id[5:]  # Strip 'supa_' prefix to get raw UUID
        return or_(column == user_id, column.like('user_%'), column == raw_uuid)
    return column == user_id


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

        logger.info(f"[Auth] JWT algorithm: {token_algorithm}")

        # Get appropriate key for verification
        if token_algorithm == 'ES256':
            # ES256 tokens - use public key from JWKS
            verification_key = await get_supabase_public_key()
            algorithms = ['ES256', 'RS256']  # Support both EC and RSA
            logger.info("[Auth] Using public key verification (ES256/RS256)")
        else:
            # HS256 tokens - use shared secret
            if not SUPABASE_JWT_SECRET:
                raise HTTPException(
                    status_code=500,
                    detail="Server misconfiguration: JWT secret not set"
                )
            verification_key = SUPABASE_JWT_SECRET
            algorithms = ['HS256']
            logger.info("[Auth] Using shared secret verification (HS256)")

        # Decode and validate JWT with appropriate key and algorithm
        payload = jwt.decode(
            token,
            verification_key,
            algorithms=algorithms,
            options={"verify_exp": True, "verify_aud": False}  # Verify token hasn't expired, skip audience check
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
            logger.info(f"[Auth] Created new user from Supabase JWT: {user_email}")

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
        logger.error(f"[Auth] JWT validation error: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=401,
            detail=f"Authentication failed: {type(e).__name__}",
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
    logger.info(f"[Auth] Unified auth called with: auth={bool(authorization)}, api_key={bool(x_api_key)}, user_id={bool(x_user_id)}")

    # Try Supabase JWT authentication first
    if authorization:
        try:
            logger.info(f"[Auth] Attempting JWT auth with token: {authorization[:30]}...")
            user = await get_current_user_from_jwt(authorization, db)
            logger.info(f"[Auth] JWT auth succeeded for user: {user.email}")
            return (user, f"supa_{user.supabase_id}")
        except HTTPException as e:
            logger.warning(f"[Auth] JWT auth failed: {e.detail}")
            pass  # Fall through to next method
        except Exception as e:
            logger.warning(f"[Auth] JWT auth error: {type(e).__name__}: {str(e)}")
            pass  # Fall through to next method

    # Try API key authentication
    if x_api_key:
        try:
            user = await get_current_user(x_api_key, db)
            return (user, f"user_{user.id}")
        except HTTPException:
            pass  # Fall through to next method

    # Fall back to session-based user ID
    if x_user_id and (x_user_id.startswith('user_') or x_user_id.startswith('supa_')):
        return (None, x_user_id)

    # No valid authentication provided
    raise HTTPException(
        status_code=401,
        detail="Authentication required. Provide Authorization Bearer token, X-API-Key, or X-User-ID header."
    )


async def get_current_user_from_form(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
) -> tuple[Optional[User], str]:
    """
    Unified authentication for file uploads - checks BOTH headers AND form fields

    iOS has known issues with custom headers on multipart/form-data requests.
    This dependency checks headers first, then falls back to form fields.

    Accepts auth from:
    1. Headers: Authorization, X-API-Key, X-User-ID (standard)
    2. Form fields: authorization, x_user_id (iOS mobile fallback)

    Returns: (user_object_or_None, user_id_string)
    """
    logger.info(f"[Auth] Form auth called - Headers: auth={bool(authorization)}, api_key={bool(x_api_key)}, user_id={bool(x_user_id)}")

    # First try standard header-based auth
    try:
        return await get_current_user_unified(authorization, x_api_key, x_user_id, db)
    except HTTPException as header_error:
        logger.warning(f"[Auth] Header auth failed: {header_error.detail}")
        logger.info("[Auth] Checking form fields for iOS mobile compatibility...")

        # iOS fallback: Check form fields
        try:
            # Read form data (for multipart/form-data requests)
            form = await request.form()
            logger.info(f"[Auth] Form fields received: {list(form.keys())}")

            # Check for authorization token in form
            form_auth = form.get('authorization')
            form_user_id = form.get('x_user_id')

            logger.info(f"[Auth] Form fields: authorization={bool(form_auth)}, x_user_id={bool(form_user_id)}")

            if form_auth:
                # Try JWT authentication from form field
                logger.info(f"[Auth] Attempting JWT auth from form field: {str(form_auth)[:30]}...")
                user = await get_current_user_from_jwt(str(form_auth), db)
                logger.info(f"[Auth] Form JWT auth succeeded for user: {user.email}")
                return (user, f"supa_{user.supabase_id}")

            if form_user_id:
                # Fall back to session ID from form
                user_id_str = str(form_user_id)
                if user_id_str.startswith('user_') or user_id_str.startswith('supa_'):
                    logger.info(f"[Auth] Using form user_id: {user_id_str[:20]}...")
                    return (None, user_id_str)

            # No valid form auth found either
            logger.info("[Auth] No valid auth in headers OR form fields")
            raise header_error  # Re-raise original error

        except HTTPException:
            raise  # Re-raise auth errors
        except Exception as e:
            logger.error(f"[Auth] Form parsing error: {type(e).__name__}: {str(e)}")
            raise header_error  # Re-raise original header error if form parsing fails
