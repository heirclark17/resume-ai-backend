from pydantic_settings import BaseSettings
from functools import lru_cache
import os

class Settings(BaseSettings):
    # API Keys
    claude_api_key: str = ""
    openai_api_key: str = ""
    perplexity_api_key: str = ""

    # Test Mode
    test_mode: bool = False

    # File Storage
    upload_dir: str = "./uploads"
    resumes_dir: str = "./resumes"

    # App Settings
    app_name: str = "ResumeAI"
    app_version: str = "1.0.0"
    debug: bool = True

    # API Settings
    backend_host: str = "0.0.0.0"  # Changed to 0.0.0.0 for Railway
    backend_port: int = int(os.getenv("PORT", "8000"))  # Railway provides PORT env var

    class Config:
        env_file = ".env"

    @property
    def database_url(self) -> str:
        """
        Get database URL with proper async driver
        Railway provides DATABASE_URL as postgres:// or postgresql://
        We need to convert it to postgresql+asyncpg:// for async support
        """
        railway_db = os.getenv("DATABASE_URL")

        if railway_db:
            print(f"[CONFIG] Railway DATABASE_URL detected: {railway_db[:30]}...")
            # Convert to async driver
            if railway_db.startswith("postgres://"):
                url = railway_db.replace("postgres://", "postgresql+asyncpg://", 1)
                print(f"[CONFIG] Converted to: {url[:30]}...")
                return url
            elif railway_db.startswith("postgresql://"):
                url = railway_db.replace("postgresql://", "postgresql+asyncpg://", 1)
                print(f"[CONFIG] Converted to: {url[:30]}...")
                return url
            else:
                print(f"[CONFIG] Using DATABASE_URL as-is")
                return railway_db
        else:
            print("[CONFIG] No DATABASE_URL found, using SQLite")
            return "sqlite+aiosqlite:///./database/resume_ai.db"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
