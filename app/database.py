from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import get_settings

settings = get_settings()

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True
)

# Create session factory
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base class for models
Base = declarative_base()

# Dependency for FastAPI routes
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session

# Initialize database (create tables)
async def init_db():
    """Create all database tables and run migrations"""
    # Import models to register them with Base
    from app.models import resume, job, company, user, interview_prep, star_story, analysis_cache, career_plan, application

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created")

    # Run migrations for existing tables
    await run_migrations()


async def run_migrations():
    """Run schema migrations for existing tables"""
    from sqlalchemy import text

    # Columns to add to interview_preps table
    interview_prep_columns = [
        'readiness_score_data',
        'values_alignment_data',
        'company_research_data',
        'strategic_news_data',
        'competitive_intelligence_data',
        'interview_strategy_data',
        'executive_insights_data',
        'certification_recommendations_data'
    ]

    async with engine.begin() as conn:
        # Check if we're using PostgreSQL or SQLite
        db_url = str(settings.database_url)
        is_postgres = 'postgresql' in db_url

        for col in interview_prep_columns:
            try:
                if is_postgres:
                    # PostgreSQL syntax
                    await conn.execute(text(f"ALTER TABLE interview_preps ADD COLUMN IF NOT EXISTS {col} JSONB DEFAULT NULL"))
                else:
                    # SQLite - check if column exists first
                    result = await conn.execute(text(f"PRAGMA table_info(interview_preps)"))
                    existing_cols = [row[1] for row in result.fetchall()]
                    if col not in existing_cols:
                        await conn.execute(text(f"ALTER TABLE interview_preps ADD COLUMN {col} TEXT"))
                print(f"  Migration: ensured column {col} exists")
            except Exception as e:
                # Column might already exist or table doesn't exist yet
                pass

    print("Migrations completed")
