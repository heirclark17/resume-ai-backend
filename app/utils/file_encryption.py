import os
from cryptography.fernet import Fernet
from pathlib import Path
from typing import Union


class FileEncryption:
    """Handle file encryption/decryption at rest using Fernet (AES-256)"""

    def __init__(self):
        """Initialize encryption with key from environment or generate new one"""
        # Get encryption key from environment or generate
        encryption_key_str = os.getenv("FILE_ENCRYPTION_KEY")

        if encryption_key_str:
            self.key = encryption_key_str.encode()
        else:
            # Generate new key if not found (WARNING: will make old files unreadable)
            self.key = Fernet.generate_key()
            print(f"WARNING: Generated new encryption key. Set FILE_ENCRYPTION_KEY in env:")
            print(f"FILE_ENCRYPTION_KEY={self.key.decode()}")

        self.cipher = Fernet(self.key)

    def encrypt_file(self, file_path: Union[str, Path]) -> bool:
        """
        Encrypt file in place (replaces original with encrypted version)

        Args:
            file_path: Path to file to encrypt

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            file_path = Path(file_path)

            # Read plaintext file
            with open(file_path, 'rb') as f:
                plaintext = f.read()

            # Encrypt
            ciphertext = self.cipher.encrypt(plaintext)

            # Write back encrypted version
            with open(file_path, 'wb') as f:
                f.write(ciphertext)

            return True

        except Exception as e:
            print(f"[Encryption] Failed to encrypt {file_path}: {e}")
            return False

    def decrypt_file(self, file_path: Union[str, Path]) -> bytes:
        """
        Decrypt file and return contents (does NOT modify file on disk)

        Args:
            file_path: Path to encrypted file

        Returns:
            bytes: Decrypted file contents

        Raises:
            Exception: If decryption fails
        """
        try:
            file_path = Path(file_path)

            # Read encrypted file
            with open(file_path, 'rb') as f:
                ciphertext = f.read()

            # Decrypt
            plaintext = self.cipher.decrypt(ciphertext)

            return plaintext

        except Exception as e:
            # Try returning raw file (might be unencrypted legacy file)
            print(f"[Decryption] Failed to decrypt {file_path}, returning raw: {e}")
            with open(file_path, 'rb') as f:
                return f.read()

    def encrypt_bytes(self, data: bytes) -> bytes:
        """Encrypt bytes in memory"""
        return self.cipher.encrypt(data)

    def decrypt_bytes(self, ciphertext: bytes) -> bytes:
        """Decrypt bytes in memory"""
        try:
            return self.cipher.decrypt(ciphertext)
        except Exception:
            # Return raw if decryption fails (unencrypted data)
            return ciphertext

    @staticmethod
    def generate_key() -> str:
        """Generate a new encryption key (for setup)"""
        key = Fernet.generate_key()
        return key.decode()
