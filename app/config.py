from pydantic_settings import BaseSettings
from functools import lru_cache
import os

class Settings(BaseSettings):
    # API Keys
    claude_api_key: str = ""
    perplexity_api_key: str = ""

    # Test Mode
    test_mode: bool = False

    # Database - Railway provides DATABASE_URL, fallback to SQLite for local
    database_url: str = None

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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Auto-detect database URL
        if self.database_url is None:
            # Check for Railway's DATABASE_URL (PostgreSQL)
            railway_db = os.getenv("DATABASE_URL")
            if railway_db:
                # Railway uses postgres:// or postgresql://, but SQLAlchemy async needs postgresql+asyncpg://
                if railway_db.startswith("postgres://"):
                    self.database_url = railway_db.replace("postgres://", "postgresql+asyncpg://", 1)
                elif railway_db.startswith("postgresql://"):
                    self.database_url = railway_db.replace("postgresql://", "postgresql+asyncpg://", 1)
                else:
                    self.database_url = railway_db
            else:
                # Fallback to local SQLite
                self.database_url = "sqlite+aiosqlite:///./database/resume_ai.db"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
