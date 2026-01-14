import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional
from fastapi import UploadFile, HTTPException
from app.utils.file_encryption import FileEncryption
from app.utils.file_integrity import FileIntegrity
from app.utils.virus_scanner import VirusScanner
import filetype

class FileHandler:
    """Handle file uploads and storage"""

    def __init__(self, base_dir: str = "./uploads"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)

        # Create subdirectories
        self.resumes_dir = self.base_dir / "resumes"
        self.resumes_dir.mkdir(exist_ok=True)

        # Initialize encryption
        self.encryption = FileEncryption()

        # Initialize file integrity (HMAC signatures)
        self.integrity = FileIntegrity()

        # Initialize virus scanner
        self.virus_scanner = VirusScanner()

    async def save_upload(self, file: UploadFile, category: str = "resumes") -> dict:
        """
        Save uploaded file to disk with size validation BEFORE write

        Args:
            file: UploadFile from FastAPI
            category: Subdirectory (resumes, exports, etc.)

        Returns:
            dict with file_path, filename, size
        """
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")

        # Validate file type
        allowed_extensions = {'.docx', '.pdf'}
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed: {allowed_extensions}"
            )

        # Validate size BEFORE writing (check Content-Length header)
        max_size = 10 * 1024 * 1024  # 10MB
        if hasattr(file, 'size') and file.size is not None:
            if file.size > max_size:
                raise HTTPException(
                    status_code=400,
                    detail=f"File too large ({file.size} bytes). Maximum allowed: {max_size} bytes (10MB)"
                )

        # Create unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{file.filename}"

        # Determine save path
        save_dir = self.base_dir / category
        save_dir.mkdir(exist_ok=True)
        file_path = save_dir / safe_filename

        # Save file with streaming size limit
        try:
            bytes_written = 0
            with file_path.open("wb") as buffer:
                while chunk := await file.read(8192):  # Read 8KB chunks
                    bytes_written += len(chunk)

                    # Check size limit during streaming
                    if bytes_written > max_size:
                        buffer.close()
                        file_path.unlink()  # Delete partial file
                        raise HTTPException(
                            status_code=400,
                            detail=f"File exceeds maximum size of {max_size} bytes (10MB)"
                        )

                    buffer.write(chunk)
        except HTTPException:
            # Re-raise our size limit exception
            raise
        except Exception as e:
            # Clean up partial file on error
            if file_path.exists():
                file_path.unlink()
            raise HTTPException(status_code=500, detail=f"File save failed: {str(e)}")

        # Get final file size (before encryption)
        file_size = file_path.stat().st_size

        # Validate MIME type using magic bytes (not just extension)
        kind = filetype.guess(str(file_path))
        if kind is None:
            # File type could not be determined
            file_path.unlink()  # Delete file
            raise HTTPException(
                status_code=400,
                detail="Could not determine file type. File may be corrupted or unsupported."
            )

        # Verify file type matches expected types
        allowed_mimes = {
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # .docx
            'application/pdf'  # .pdf
        }

        if kind.mime not in allowed_mimes:
            file_path.unlink()  # Delete file
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Detected: {kind.mime}. Expected: DOCX or PDF"
            )

        # Verify extension matches detected MIME type
        expected_ext = {
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
            'application/pdf': '.pdf'
        }

        if file_ext != expected_ext.get(kind.mime, ''):
            file_path.unlink()  # Delete file
            raise HTTPException(
                status_code=400,
                detail=f"File extension mismatch. Extension: {file_ext}, Detected type: {kind.mime}"
            )

        # Scan for viruses/malware before encryption
        is_safe, threat_name = self.virus_scanner.scan_file(str(file_path))
        if not is_safe:
            file_path.unlink()  # Delete infected file
            raise HTTPException(
                status_code=400,
                detail=f"File rejected: Potential threat detected ({threat_name}). Please ensure your file is clean and try again."
            )

        # Encrypt file at rest for security
        encryption_success = self.encryption.encrypt_file(file_path)
        if not encryption_success:
            print(f"WARNING:  WARNING: Failed to encrypt {file_path}, file saved as plaintext")

        # Generate HMAC signature for file integrity verification (after encryption)
        file_signature = self.integrity.generate_signature(file_path)
        if not file_signature:
            print(f"WARNING:  WARNING: Failed to generate signature for {file_path}")

        return {
            "file_path": str(file_path),
            "filename": safe_filename,
            "size": file_size,
            "encrypted": encryption_success,
            "signature": file_signature  # HMAC-SHA256 signature for integrity verification
        }

    def delete_file(self, file_path: str) -> bool:
        """Delete file from disk"""
        try:
            Path(file_path).unlink(missing_ok=True)
            return True
        except Exception:
            return False

    def cleanup_old_files(self, days: int = 30):
        """Delete files older than N days"""
        cutoff_time = datetime.now().timestamp() - (days * 24 * 60 * 60)

        for file_path in self.base_dir.rglob("*"):
            if file_path.is_file():
                if file_path.stat().st_mtime < cutoff_time:
                    file_path.unlink()
