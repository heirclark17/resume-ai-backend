import hmac
import hashlib
import os
from pathlib import Path
from typing import Optional


class FileIntegrity:
    """Handle HMAC signatures for file integrity verification"""

    def __init__(self):
        """Initialize with secret key from environment"""
        # Get HMAC secret from environment or generate
        self.secret = os.getenv("FILE_INTEGRITY_SECRET")

        if not self.secret:
            # Generate new secret if not found
            self.secret = os.urandom(32).hex()
            print(f"WARNING: Generated new file integrity secret. Set FILE_INTEGRITY_SECRET in env:")
            print(f"FILE_INTEGRITY_SECRET={self.secret}")

        # Convert to bytes if string
        if isinstance(self.secret, str):
            self.secret = self.secret.encode('utf-8')

    def generate_signature(self, file_path: str) -> str:
        """
        Generate HMAC-SHA256 signature for a file

        Args:
            file_path: Path to the file

        Returns:
            str: Hex-encoded HMAC signature
        """
        try:
            file_path = Path(file_path)

            # Read file contents
            with open(file_path, 'rb') as f:
                file_data = f.read()

            # Generate HMAC-SHA256 signature
            signature = hmac.new(
                self.secret,
                file_data,
                hashlib.sha256
            ).hexdigest()

            return signature

        except Exception as e:
            print(f"[File Integrity] Failed to generate signature for {file_path}: {e}")
            return ""

    def verify_signature(self, file_path: str, expected_signature: str) -> bool:
        """
        Verify HMAC signature for a file

        Args:
            file_path: Path to the file
            expected_signature: Expected HMAC signature (hex-encoded)

        Returns:
            bool: True if signature is valid, False otherwise
        """
        try:
            actual_signature = self.generate_signature(file_path)

            if not actual_signature:
                return False

            # Use constant-time comparison to prevent timing attacks
            return hmac.compare_digest(actual_signature, expected_signature)

        except Exception as e:
            print(f"[File Integrity] Verification failed for {file_path}: {e}")
            return False

    def sign_file_metadata(self, file_path: str, metadata: dict) -> str:
        """
        Generate signature for file + metadata combined

        Args:
            file_path: Path to the file
            metadata: Additional metadata to include in signature (e.g., user_id, timestamp)

        Returns:
            str: Hex-encoded HMAC signature
        """
        try:
            file_path = Path(file_path)

            # Read file contents
            with open(file_path, 'rb') as f:
                file_data = f.read()

            # Combine file data with metadata
            metadata_str = str(sorted(metadata.items())).encode('utf-8')
            combined_data = file_data + metadata_str

            # Generate HMAC-SHA256 signature
            signature = hmac.new(
                self.secret,
                combined_data,
                hashlib.sha256
            ).hexdigest()

            return signature

        except Exception as e:
            print(f"[File Integrity] Failed to generate metadata signature for {file_path}: {e}")
            return ""
