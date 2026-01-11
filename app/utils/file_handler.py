import os
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional
from fastapi import UploadFile, HTTPException

class FileHandler:
    """Handle file uploads and storage"""

    def __init__(self, base_dir: str = "./uploads"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)

        # Create subdirectories
        self.resumes_dir = self.base_dir / "resumes"
        self.resumes_dir.mkdir(exist_ok=True)

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

        # Get final file size
        file_size = file_path.stat().st_size

        return {
            "file_path": str(file_path),
            "filename": safe_filename,
            "size": file_size
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
