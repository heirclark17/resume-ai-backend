import os
import subprocess
from pathlib import Path
from typing import Optional, Tuple


class VirusScanner:
    """
    Virus scanning integration for uploaded files

    Supports ClamAV if installed, otherwise provides basic file validation.
    This is a LOW-RISK security enhancement.
    """

    def __init__(self):
        """Initialize scanner and check if ClamAV is available"""
        self.clamav_available = self._check_clamav_availability()

        if self.clamav_available:
            print("[Virus Scanner] ClamAV detected and available")
        else:
            print("[Virus Scanner] ClamAV not available - using basic file validation only")
            print("[Virus Scanner] To enable virus scanning, install ClamAV:")
            print("  - Linux: sudo apt-get install clamav clamav-daemon")
            print("  - macOS: brew install clamav")
            print("  - Windows: Download from https://www.clamav.net/downloads")

    def _check_clamav_availability(self) -> bool:
        """Check if clamscan command is available"""
        try:
            result = subprocess.run(
                ['clamscan', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            return False

    def scan_file(self, file_path: str) -> Tuple[bool, Optional[str]]:
        """
        Scan file for viruses/malware

        Args:
            file_path: Path to file to scan

        Returns:
            Tuple[bool, Optional[str]]: (is_safe, threat_name)
                - is_safe: True if file is clean, False if infected
                - threat_name: Name of detected threat, or None if clean
        """
        file_path = Path(file_path)

        if not file_path.exists():
            return False, "File not found"

        # If ClamAV is available, use it
        if self.clamav_available:
            return self._scan_with_clamav(file_path)

        # Otherwise, do basic validation
        return self._basic_file_validation(file_path)

    def _scan_with_clamav(self, file_path: Path) -> Tuple[bool, Optional[str]]:
        """Scan file using ClamAV"""
        try:
            result = subprocess.run(
                ['clamscan', '--no-summary', str(file_path)],
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )

            # ClamAV returns 0 if clean, 1 if infected
            if result.returncode == 0:
                print(f"[Virus Scanner] File clean: {file_path.name}")
                return True, None
            elif result.returncode == 1:
                # Extract threat name from output
                threat_name = "Unknown threat"
                if "FOUND" in result.stdout:
                    # Parse output like: "file.pdf: Eicar-Signature FOUND"
                    parts = result.stdout.split(":")
                    if len(parts) >= 2:
                        threat_name = parts[1].replace("FOUND", "").strip()

                print(f"[Virus Scanner] WARNING:  THREAT DETECTED: {threat_name} in {file_path.name}")
                return False, threat_name
            else:
                # Error occurred during scanning
                print(f"[Virus Scanner] Error scanning file: {result.stderr}")
                # For security, treat scan errors as suspicious
                return False, "Scan error - file rejected for safety"

        except subprocess.TimeoutExpired:
            print(f"[Virus Scanner] Scan timeout for {file_path.name}")
            return False, "Scan timeout - file too large or complex"
        except Exception as e:
            print(f"[Virus Scanner] Scan exception: {e}")
            return False, f"Scan error: {str(e)}"

    def _basic_file_validation(self, file_path: Path) -> Tuple[bool, Optional[str]]:
        """
        Basic file validation when ClamAV is not available

        Checks for suspicious patterns and file characteristics
        """
        try:
            # Check file size (reject files over 100MB as suspicious)
            file_size = file_path.stat().st_size
            if file_size > 100 * 1024 * 1024:  # 100MB
                print(f"[Virus Scanner] File too large: {file_size} bytes")
                return False, "File too large (>100MB)"

            # Read first few bytes to check for known malicious signatures
            with open(file_path, 'rb') as f:
                header = f.read(1024)  # First 1KB

            # Check for executable signatures
            # MZ header (Windows PE executable)
            if header.startswith(b'MZ'):
                print(f"[Virus Scanner] Executable detected: {file_path.name}")
                return False, "Executable file detected"

            # ELF header (Linux executable)
            if header.startswith(b'\x7FELF'):
                print(f"[Virus Scanner] Linux executable detected: {file_path.name}")
                return False, "Linux executable detected"

            # Mach-O header (macOS executable)
            if header.startswith(b'\xFE\xED\xFA\xCE') or header.startswith(b'\xFE\xED\xFA\xCF'):
                print(f"[Virus Scanner] macOS executable detected: {file_path.name}")
                return False, "macOS executable detected"

            # EICAR test file (standard virus test signature)
            eicar = b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'
            if eicar in header:
                print(f"[Virus Scanner] EICAR test signature detected: {file_path.name}")
                return False, "EICAR-Test-Signature"

            # If no suspicious patterns found, consider it safe
            # Note: This is NOT a comprehensive virus scan, just basic validation
            print(f"[Virus Scanner] Basic validation passed: {file_path.name}")
            return True, None

        except Exception as e:
            print(f"[Virus Scanner] Validation error: {e}")
            # For security, treat validation errors as suspicious
            return False, f"Validation error: {str(e)}"
