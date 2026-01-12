"""
Authentication Routes - Registration & 2FA Management
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.middleware.auth import get_current_user
from app.utils.two_factor_auth import get_two_factor_auth
from app.utils.recaptcha import get_recaptcha_verifier
from app.utils.logger import get_logger

router = APIRouter()
logger = get_logger()


# Registration Models
class RegistrationRequest(BaseModel):
    email: EmailStr
    username: str
    recaptcha_token: Optional[str] = None


class RegistrationResponse(BaseModel):
    success: bool
    message: str
    api_key: str
    user_id: int


@router.post("/register", response_model=RegistrationResponse)
async def register_user(
    request: RegistrationRequest,
    http_request: Request,
    db: Session = Depends(get_db)
):
    """
    Register a new user with reCAPTCHA v3 protection

    Requires:
        - email: Valid email address
        - username: Unique username
        - recaptcha_token: Google reCAPTCHA v3 token (optional if not configured)

    Returns:
        - API key (save this - shown only once!)
        - User ID
    """
    try:
        # Verify reCAPTCHA token
        recaptcha = get_recaptcha_verifier()
        if recaptcha.is_enabled():
            if not request.recaptcha_token:
                raise HTTPException(
                    status_code=400,
                    detail="reCAPTCHA token required"
                )

            # Get client IP for verification
            client_ip = http_request.client.host if http_request.client else None

            # Verify token
            is_valid, score, error = await recaptcha.verify_token(
                token=request.recaptcha_token,
                expected_action="registration",
                remote_ip=client_ip
            )

            if not is_valid:
                logger.warning(
                    f"Registration blocked by reCAPTCHA: {error} (score: {score}, IP: {client_ip})"
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"CAPTCHA verification failed: {error}"
                )

            logger.info(f"reCAPTCHA verification passed for registration (score: {score})")

        # Check if email already exists
        result = await db.execute(select(User).where(User.email == request.email))
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")

        # Check if username already exists
        result = await db.execute(select(User).where(User.username == request.username))
        existing_username = result.scalar_one_or_none()
        if existing_username:
            raise HTTPException(status_code=400, detail="Username already taken")

        # Create new user
        new_user = User.create_user(
            email=request.email,
            username=request.username
        )

        # Get plaintext API key (stored temporarily in _plaintext_api_key attribute)
        api_key = new_user._plaintext_api_key

        # Save to database
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        logger.info(f"New user registered: {new_user.id} ({new_user.email})")

        return RegistrationResponse(
            success=True,
            message="Registration successful. Save your API key - it will not be shown again!",
            api_key=api_key,
            user_id=new_user.id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(status_code=500, detail="Registration failed")


# 2FA Request/Response Models
class TwoFactorSetupResponse(BaseModel):
    secret: str
    qr_code: str
    backup_codes: list[str]


class TwoFactorVerifyRequest(BaseModel):
    code: str


class TwoFactorVerifyResponse(BaseModel):
    success: bool
    message: str


class TwoFactorStatusResponse(BaseModel):
    enabled: bool
    remaining_backup_codes: int


class BackupCodesResponse(BaseModel):
    backup_codes: list[str]


@router.post("/2fa/setup", response_model=TwoFactorSetupResponse)
async def setup_two_factor(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate TOTP secret and QR code for 2FA setup

    Returns:
        - secret: TOTP secret (for manual entry)
        - qr_code: Base64-encoded QR code image
        - backup_codes: List of one-time backup codes
    """
    try:
        two_fa = get_two_factor_auth()

        # Check if 2FA is already enabled
        if current_user.twofa_enabled:
            raise HTTPException(
                status_code=400,
                detail="2FA is already enabled. Disable it first to regenerate."
            )

        # Generate TOTP secret
        secret = two_fa.generate_totp_secret()

        # Generate QR code
        qr_code = two_fa.generate_qr_code(
            secret=secret,
            user_email=current_user.email,
            issuer_name="ResumeAI"
        )

        # Generate backup codes
        backup_codes = two_fa.generate_backup_codes(count=10)

        # Encrypt and store secret (not yet enabled)
        encrypted_secret = two_fa.encrypt_secret(secret)
        encrypted_backup_codes = two_fa.encrypt_backup_codes(backup_codes)

        # Update user record (but dont enable 2FA yet)
        current_user.totp_secret = encrypted_secret
        current_user.twofa_backup_codes = encrypted_backup_codes
        current_user.twofa_enabled = False  # Not enabled until verified

        db.commit()

        logger.info(f"2FA setup initiated for user {current_user.id}")

        return TwoFactorSetupResponse(
            secret=secret,
            qr_code=qr_code,
            backup_codes=backup_codes
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"2FA setup error for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to set up 2FA")


@router.post("/2fa/verify", response_model=TwoFactorVerifyResponse)
async def verify_two_factor(
    request: TwoFactorVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verify TOTP code and enable 2FA

    Requires:
        - code: 6-digit TOTP code from authenticator app
    """
    try:
        two_fa = get_two_factor_auth()

        # Check if secret exists
        if not current_user.totp_secret:
            raise HTTPException(
                status_code=400,
                detail="2FA not set up. Call /api/auth/2fa/setup first."
            )

        # Decrypt secret
        secret = two_fa.decrypt_secret(current_user.totp_secret)

        # Verify TOTP code
        is_valid = two_fa.verify_totp_code(secret, request.code)

        if not is_valid:
            logger.warning(f"Invalid 2FA code attempt for user {current_user.id}")
            raise HTTPException(status_code=400, detail="Invalid verification code")

        # Enable 2FA
        current_user.twofa_enabled = True
        db.commit()

        logger.info(f"2FA enabled for user {current_user.id}")

        return TwoFactorVerifyResponse(
            success=True,
            message="Two-factor authentication enabled successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"2FA verification error for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to verify 2FA code")


@router.post("/2fa/disable", response_model=TwoFactorVerifyResponse)
async def disable_two_factor(
    request: TwoFactorVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Disable 2FA (requires TOTP code for security)

    Requires:
        - code: 6-digit TOTP code or backup code
    """
    try:
        two_fa = get_two_factor_auth()

        # Check if 2FA is enabled
        if not current_user.twofa_enabled:
            raise HTTPException(status_code=400, detail="2FA is not enabled")

        # Decrypt secret
        secret = two_fa.decrypt_secret(current_user.totp_secret)

        # Verify TOTP code or backup code
        is_valid_totp = two_fa.verify_totp_code(secret, request.code)
        is_valid_backup = False

        if not is_valid_totp and current_user.twofa_backup_codes:
            is_valid_backup, _ = two_fa.verify_backup_code(
                current_user.twofa_backup_codes,
                request.code
            )

        if not is_valid_totp and not is_valid_backup:
            logger.warning(f"Invalid 2FA code for disable attempt - user {current_user.id}")
            raise HTTPException(status_code=400, detail="Invalid verification code")

        # Disable 2FA and clear secrets
        current_user.twofa_enabled = False
        current_user.totp_secret = None
        current_user.twofa_backup_codes = None
        db.commit()

        logger.info(f"2FA disabled for user {current_user.id}")

        return TwoFactorVerifyResponse(
            success=True,
            message="Two-factor authentication disabled successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"2FA disable error for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to disable 2FA")


@router.post("/2fa/backup-codes", response_model=BackupCodesResponse)
async def regenerate_backup_codes(
    request: TwoFactorVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Regenerate backup codes (requires TOTP code for security)

    Requires:
        - code: 6-digit TOTP code from authenticator app
    """
    try:
        two_fa = get_two_factor_auth()

        # Check if 2FA is enabled
        if not current_user.twofa_enabled:
            raise HTTPException(status_code=400, detail="2FA is not enabled")

        # Decrypt secret and verify
        secret = two_fa.decrypt_secret(current_user.totp_secret)
        is_valid = two_fa.verify_totp_code(secret, request.code)

        if not is_valid:
            logger.warning(f"Invalid 2FA code for backup code regeneration - user {current_user.id}")
            raise HTTPException(status_code=400, detail="Invalid verification code")

        # Generate new backup codes
        backup_codes = two_fa.generate_backup_codes(count=10)
        encrypted_backup_codes = two_fa.encrypt_backup_codes(backup_codes)

        # Update user record
        current_user.twofa_backup_codes = encrypted_backup_codes
        db.commit()

        logger.info(f"Backup codes regenerated for user {current_user.id}")

        return BackupCodesResponse(backup_codes=backup_codes)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Backup code regeneration error for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to regenerate backup codes")


@router.get("/2fa/status", response_model=TwoFactorStatusResponse)
async def get_two_factor_status(
    current_user: User = Depends(get_current_user)
):
    """
    Check 2FA status for current user

    Returns:
        - enabled: Whether 2FA is enabled
        - remaining_backup_codes: Number of unused backup codes
    """
    try:
        remaining_codes = 0
        if current_user.twofa_enabled and current_user.twofa_backup_codes:
            two_fa = get_two_factor_auth()
            remaining_codes = two_fa.get_remaining_backup_codes(
                current_user.twofa_backup_codes
            )

        return TwoFactorStatusResponse(
            enabled=current_user.twofa_enabled,
            remaining_backup_codes=remaining_codes
        )

    except Exception as e:
        logger.error(f"2FA status check error for user {current_user.id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to check 2FA status")
