from fastapi import APIRouter, Header, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.middleware.auth import get_current_user_from_jwt, get_supabase_public_key
from typing import Optional
import jwt
import os

router = APIRouter(prefix="/debug", tags=["auth-debug"])

@router.get("/test-jwt")
async def test_jwt_verification(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db)
):
    """Test JWT verification with detailed error reporting"""
    
    if not authorization:
        return {"error": "No Authorization header provided"}
    
    # Extract token
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        return {"error": "Invalid Authorization header format"}
    
    token = parts[1]
    
    try:
        # Step 1: Decode header (unverified)
        unverified_header = jwt.get_unverified_header(token)
        algorithm = unverified_header.get('alg', 'UNKNOWN')
        
        # Step 2: Decode payload (unverified)
        unverified_payload = jwt.decode(token, options={"verify_signature": False})
        
        # Step 3: Get JWKS public key
        supabase_url = os.getenv('SUPABASE_URL', '')
        supabase_anon_key = os.getenv('SUPABASE_ANON_KEY', '')
        
        verification_key = await get_supabase_public_key()
        
        # Step 4: Try to verify
        try:
            verified_payload = jwt.decode(
                token,
                verification_key,
                algorithms=['ES256', 'RS256', 'HS256'],
                options={"verify_exp": True}
            )
            verification_status = "SUCCESS"
            verification_error = None
        except Exception as e:
            verification_status = "FAILED"
            verification_error = str(e)
            verified_payload = None
        
        return {
            "status": "JWT Analysis Complete",
            "token_prefix": token[:50] + "...",
            "header": {
                "algorithm": algorithm,
                "type": unverified_header.get('typ'),
            },
            "payload_unverified": {
                "sub": unverified_payload.get('sub'),
                "email": unverified_payload.get('email'),
                "role": unverified_payload.get('role'),
                "iss": unverified_payload.get('iss'),
                "aud": unverified_payload.get('aud'),
                "exp": unverified_payload.get('exp'),
            },
            "backend_config": {
                "supabase_url": bool(supabase_url),
                "supabase_anon_key": bool(supabase_anon_key),
                "anon_key_length": len(supabase_anon_key),
            },
            "verification": {
                "status": verification_status,
                "error": verification_error,
                "verified_payload": verified_payload if verified_payload else None,
            }
        }
        
    except Exception as e:
        return {
            "error": f"JWT Analysis Failed: {type(e).__name__}: {str(e)}",
            "token_prefix": token[:50] + "..." if len(token) > 50 else token,
        }
