"""
Two-Factor Authentication (2FA) Utility
TOTP-based two-factor authentication using PyOTP
"""

import pyotp
import qrcode
import io
import base64
import secrets
import json
from typing import Tuple, List, Optional
from datetime import datetime
from cryptography.fernet import Fernet
import os


class TwoFactorAuth:
    """Handle TOTP-based two-factor authentication"""

    def __init__(self):
        # Get encryption key for storing secrets
        encryption_key = os.getenv("ENCRYPTION_KEY")
        if not encryption_key:
            raise ValueError("ENCRYPTION_KEY environment variable not set")
        self.cipher = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)

    def generate_totp_secret(self) -> str:
        """
        Generate a new TOTP secret (base32 encoded)

        Returns:
            str: Base32-encoded secret key
        """
        return pyotp.random_base32()

    def generate_qr_code(self, secret: str, user_email: str, issuer_name: str = "ResumeAI") -> str:
        """
        Generate QR code for authenticator app setup

        Args:
            secret: TOTP secret key
            user_email: User's email address
            issuer_name: Name of the application

        Returns:
            str: Base64-encoded PNG image
        """
        # Create provisioning URI
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user_email,
            issuer_name=issuer_name
        )

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(provisioning_uri)
        qr.make(fit=True)

        # Convert to image
        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

        return f"data:image/png;base64,{img_base64}"

    def verify_totp_code(self, secret: str, code: str, window: int = 1) -> bool:
        """
        Verify a TOTP code against the secret

        Args:
            secret: TOTP secret key
            code: 6-digit code from authenticator app
            window: Time window for validation (default: 1 = ±30 seconds)

        Returns:
            bool: True if code is valid
        """
        try:
            totp = pyotp.TOTP(secret)
            # Verify with time window to account for clock drift
            return totp.verify(code, valid_window=window)
        except Exception:
            return False

    def generate_backup_codes(self, count: int = 10) -> List[str]:
        """
        Generate one-time backup codes

        Args:
            count: Number of backup codes to generate

        Returns:
            List[str]: List of backup codes (format: XXXX-XXXX-XXXX)
        """
        backup_codes = []
        for _ in range(count):
            # Generate 12-character code with dashes
            code_parts = [
                secrets.token_hex(2).upper(),
                secrets.token_hex(2).upper(),
                secrets.token_hex(2).upper()
            ]
            backup_codes.append('-'.join(code_parts))
        return backup_codes

    def encrypt_secret(self, secret: str) -> str:
        """
        Encrypt TOTP secret for database storage

        Args:
            secret: Plain text TOTP secret

        Returns:
            str: Encrypted secret
        """
        encrypted = self.cipher.encrypt(secret.encode('utf-8'))
        return encrypted.decode('utf-8')

    def decrypt_secret(self, encrypted_secret: str) -> str:
        """
        Decrypt TOTP secret from database

        Args:
            encrypted_secret: Encrypted secret from database

        Returns:
            str: Decrypted TOTP secret
        """
        decrypted = self.cipher.decrypt(encrypted_secret.encode('utf-8'))
        return decrypted.decode('utf-8')

    def encrypt_backup_codes(self, backup_codes: List[str]) -> str:
        """
        Encrypt backup codes for database storage

        Args:
            backup_codes: List of backup codes

        Returns:
            str: Encrypted JSON string
        """
        # Store with usage tracking
        codes_data = {
            "codes": backup_codes,
            "used": [],
            "generated_at": datetime.utcnow().isoformat()
        }
        json_data = json.dumps(codes_data)
        encrypted = self.cipher.encrypt(json_data.encode('utf-8'))
        return encrypted.decode('utf-8')

    def decrypt_backup_codes(self, encrypted_codes: str) -> dict:
        """
        Decrypt backup codes from database

        Args:
            encrypted_codes: Encrypted backup codes JSON

        Returns:
            dict: Backup codes data with usage tracking
        """
        decrypted = self.cipher.decrypt(encrypted_codes.encode('utf-8'))
        return json.loads(decrypted.decode('utf-8'))

    def verify_backup_code(self, encrypted_codes: str, code: str) -> Tuple[bool, Optional[str]]:
        """
        Verify and consume a backup code

        Args:
            encrypted_codes: Encrypted backup codes from database
            code: Backup code to verify

        Returns:
            Tuple[bool, Optional[str]]: (is_valid, updated_encrypted_codes)
        """
        try:
            codes_data = self.decrypt_backup_codes(encrypted_codes)

            # Check if code exists and hasn't been used
            if code in codes_data["codes"] and code not in codes_data["used"]:
                # Mark as used
                codes_data["used"].append(code)

                # Re-encrypt updated data
                json_data = json.dumps(codes_data)
                encrypted = self.cipher.encrypt(json_data.encode('utf-8'))
                updated_encrypted = encrypted.decode('utf-8')

                return True, updated_encrypted

            return False, None
        except Exception:
            return False, None

    def get_remaining_backup_codes(self, encrypted_codes: str) -> int:
        """
        Get count of remaining (unused) backup codes

        Args:
            encrypted_codes: Encrypted backup codes from database

        Returns:
            int: Number of remaining backup codes
        """
        try:
            codes_data = self.decrypt_backup_codes(encrypted_codes)
            total = len(codes_data["codes"])
            used = len(codes_data["used"])
            return total - used
        except Exception:
            return 0


# Singleton instance
_two_factor_auth_instance = None


def get_two_factor_auth() -> TwoFactorAuth:
    """Get singleton TwoFactorAuth instance"""
    global _two_factor_auth_instance
    if _two_factor_auth_instance is None:
        _two_factor_auth_instance = TwoFactorAuth()
    return _two_factor_auth_instance
