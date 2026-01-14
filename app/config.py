from pydantic_settings import BaseSettings
from functools import lru_cache
import os

class Settings(BaseSettings):
    # API Keys
    openai_api_key: str = ""
    perplexity_api_key: str = ""
    firecrawl_api_key: str = ""
    claude_api_key: str = ""  # For backward compatibility with .env

    # Test Mode - explicitly read from environment
    test_mode: bool = os.getenv("TEST_MODE", "false").lower() == "true"

    # File Storage
    upload_dir: str = "./uploads"
    resumes_dir: str = "./resumes"

    # App Settings
    app_name: str = "ResumeAI"
    app_version: str = "1.0.0"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"

    # CORS Settings
    allowed_origins: str = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:3000,https://talor-web.vercel.app,https://talorme.com"  # Local dev + production
    )

    # API Settings
    backend_host: str = "0.0.0.0"  # Changed to 0.0.0.0 for Railway
    backend_port: int = int(os.getenv("PORT", "8000"))  # Railway provides PORT env var

    class Config:
        env_file = ".env"
        extra = "ignore"  # Ignore extra fields from .env

    @property
    def database_url(self) -> str:
        """
        Get database URL with proper async driver
        Railway provides DATABASE_URL as postgres:// or postgresql://
        We need to convert it to postgresql+asyncpg:// for async support
        """
        railway_db = os.getenv("DATABASE_URL")

        if railway_db:
            # Sanitize URL for logging (hide credentials)
            sanitized = self._sanitize_db_url(railway_db)
            print(f"[CONFIG] Railway DATABASE_URL detected: {sanitized}")

            # Convert to async driver
            if railway_db.startswith("postgres://"):
                url = railway_db.replace("postgres://", "postgresql+asyncpg://", 1)
                print(f"[CONFIG] Converted to: {self._sanitize_db_url(url)}")
                return url
            elif railway_db.startswith("postgresql://"):
                url = railway_db.replace("postgresql://", "postgresql+asyncpg://", 1)
                print(f"[CONFIG] Converted to: {self._sanitize_db_url(url)}")
                return url
            else:
                print(f"[CONFIG] Using DATABASE_URL as-is")
                return railway_db
        else:
            print("[CONFIG] No DATABASE_URL found, using SQLite")
            return "sqlite+aiosqlite:///./database/resume_ai.db"

    @staticmethod
    def _sanitize_db_url(url: str) -> str:
        """Sanitize database URL by masking credentials"""
        import re
        # Pattern: postgresql://username:password@host:port/database
        # Replace password with ***
        pattern = r"(postgresql[+\w]*://[^:]+:)([^@]+)(@.+)"
        sanitized = re.sub(pattern, r"\1***\3", url)
        return sanitized

@lru_cache()
def get_settings() -> Settings:
    return Settings()
