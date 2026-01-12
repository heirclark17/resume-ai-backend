"""
reCAPTCHA v3 Verification Utility
Server-side validation for Google reCAPTCHA v3 tokens
"""

import os
import httpx
from typing import Tuple, Optional
from app.utils.logger import get_logger

logger = get_logger()


class RecaptchaVerifier:
    """Handle Google reCAPTCHA v3 verification"""

    def __init__(self):
        # Get reCAPTCHA secret key from environment
        self.secret_key = os.getenv("RECAPTCHA_SECRET_KEY")
        self.verify_url = "https://www.google.com/recaptcha/api/siteverify"
        
        # Minimum score threshold (0.0-1.0, higher = more likely human)
        # 0.5 is recommended default, can be adjusted based on false positive rate
        self.min_score = float(os.getenv("RECAPTCHA_MIN_SCORE", "0.5"))
        
        if not self.secret_key:
            logger.warning("RECAPTCHA_SECRET_KEY not set - CAPTCHA verification disabled")
        else:
            logger.info(f"reCAPTCHA v3 verifier initialized (min_score: {self.min_score})")

    async def verify_token(
        self,
        token: str,
        expected_action: str = "registration",
        remote_ip: Optional[str] = None
    ) -> Tuple[bool, Optional[float], Optional[str]]:
        """
        Verify reCAPTCHA v3 token

        Args:
            token: reCAPTCHA token from frontend
            expected_action: Expected action name (e.g., "registration", "login")
            remote_ip: Client IP address (optional)

        Returns:
            Tuple of (is_valid, score, error_message)
            - is_valid: True if token is valid and score above threshold
            - score: Risk score (0.0-1.0, higher is better)
            - error_message: Error description if validation failed
        """
        # If reCAPTCHA not configured, skip verification
        if not self.secret_key:
            logger.debug("reCAPTCHA verification skipped (not configured)")
            return True, 1.0, None

        # Validate token format
        if not token or not isinstance(token, str):
            logger.warning("Invalid reCAPTCHA token format")
            return False, 0.0, "Invalid CAPTCHA token format"

        try:
            # Prepare verification request
            data = {
                "secret": self.secret_key,
                "response": token
            }
            
            if remote_ip:
                data["remoteip"] = remote_ip

            # Send verification request to Google
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(self.verify_url, data=data)
                response.raise_for_status()
                result = response.json()

            # Check if verification succeeded
            if not result.get("success"):
                error_codes = result.get("error-codes", [])
                logger.warning(f"reCAPTCHA verification failed: {error_codes}")
                return False, 0.0, f"CAPTCHA verification failed: {error_codes[0] if error_codes else 'unknown'}"

            # Extract score and action
            score = result.get("score", 0.0)
            action = result.get("action", "")
            hostname = result.get("hostname", "")

            # Validate action matches expected
            if expected_action and action != expected_action:
                logger.warning(
                    f"reCAPTCHA action mismatch: expected '{expected_action}', got '{action}'"
                )
                return False, score, f"CAPTCHA action mismatch (expected: {expected_action})"

            # Check score against threshold
            if score < self.min_score:
                logger.warning(
                    f"reCAPTCHA score too low: {score} < {self.min_score} (action: {action})"
                )
                return False, score, f"CAPTCHA score too low (likely bot): {score}"

            # Success
            logger.info(
                f"reCAPTCHA verification passed: score={score}, action={action}, hostname={hostname}"
            )
            return True, score, None

        except httpx.HTTPError as e:
            logger.error(f"reCAPTCHA verification HTTP error: {str(e)}")
            return False, 0.0, "CAPTCHA verification service unavailable"
        except Exception as e:
            logger.error(f"reCAPTCHA verification error: {str(e)}")
            return False, 0.0, "CAPTCHA verification failed"

    def is_enabled(self) -> bool:
        """Check if reCAPTCHA verification is enabled"""
        return bool(self.secret_key)


# Singleton instance
_recaptcha_verifier_instance: Optional[RecaptchaVerifier] = None


def get_recaptcha_verifier() -> RecaptchaVerifier:
    """Get singleton RecaptchaVerifier instance"""
    global _recaptcha_verifier_instance
    if _recaptcha_verifier_instance is None:
        _recaptcha_verifier_instance = RecaptchaVerifier()
    return _recaptcha_verifier_instance
