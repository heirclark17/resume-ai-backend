from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import get_settings

settings = get_settings()

# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
    pool_pre_ping=True,  # Detect and recycle stale/broken connections
    pool_recycle=300,  # Recycle connections every 5 minutes
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
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

# Initialize database (create tables)
async def init_db():
    """Create all database tables and run migrations"""
    # Import models to register them with Base
    from app.models import resume, job, company, user, interview_prep, star_story, analysis_cache
    from app.models import application, cover_letter, resume_version, follow_up_reminder, career_plan, saved_comparison
    from app.models import batch_job_url, template_preview, salary_cache

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Migrations for existing tables (new columns)
        from sqlalchemy import text
        await conn.execute(text(
            "ALTER TABLE cover_letters ADD COLUMN IF NOT EXISTS base_resume_id INTEGER"
        ))

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
        'certification_recommendations_data',
        # Added: columns for child component cached data and user interaction state
        'behavioral_technical_questions_data',
        'common_questions_data',
        'user_data',
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

        # Add question_key column to practice_question_responses
        try:
            if is_postgres:
                await conn.execute(text("ALTER TABLE practice_question_responses ADD COLUMN IF NOT EXISTS question_key VARCHAR(200)"))
            else:
                result = await conn.execute(text("PRAGMA table_info(practice_question_responses)"))
                existing_cols = [row[1] for row in result.fetchall()]
                if 'question_key' not in existing_cols:
                    await conn.execute(text("ALTER TABLE practice_question_responses ADD COLUMN question_key VARCHAR(200)"))
            print("  Migration: ensured column question_key exists on practice_question_responses")
        except Exception as e:
            pass

        # Add session_user_id column to jobs table
        try:
            if is_postgres:
                await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS session_user_id VARCHAR"))
            else:
                result = await conn.execute(text("PRAGMA table_info(jobs)"))
                existing_cols = [row[1] for row in result.fetchall()]
                if 'session_user_id' not in existing_cols:
                    await conn.execute(text("ALTER TABLE jobs ADD COLUMN session_user_id VARCHAR"))
            print("  Migration: ensured column session_user_id exists on jobs")
        except Exception as e:
            pass

        # Add missing columns to users table
        users_columns = {
            'supabase_id': 'VARCHAR UNIQUE',
            'username': 'VARCHAR UNIQUE',
            'totp_secret': 'VARCHAR',
            'twofa_enabled': 'BOOLEAN DEFAULT FALSE',
            'twofa_backup_codes': 'VARCHAR',
        }
        for col, col_type in users_columns.items():
            try:
                if is_postgres:
                    await conn.execute(text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {col_type}"))
                print(f"  Migration: ensured column {col} exists on users")
            except Exception as e:
                pass

        # Fix users table constraints - allow NULL for Supabase-only users
        for nullable_col in ['username', 'api_key', 'totp_secret', 'twofa_backup_codes']:
            try:
                if is_postgres:
                    await conn.execute(text(f"ALTER TABLE users ALTER COLUMN {nullable_col} DROP NOT NULL"))
                    print(f"  Migration: users.{nullable_col} now allows NULL")
            except Exception as e:
                pass

        # Ensure salary_cache table and unique index exist for existing deployments
        # (create_all above handles brand-new deployments; this handles upgrades)
        try:
            if is_postgres:
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS salary_cache (
                        id SERIAL PRIMARY KEY,
                        company VARCHAR(255) NOT NULL,
                        job_title VARCHAR(255) NOT NULL,
                        location VARCHAR(255),
                        median_salary VARCHAR(100),
                        salary_range VARCHAR(200),
                        market_insights TEXT,
                        sources TEXT,
                        created_at TIMESTAMP DEFAULT NOW() NOT NULL,
                        updated_at TIMESTAMP DEFAULT NOW() NOT NULL
                    )
                """))
                await conn.execute(text("""
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_salary_cache_key
                    ON salary_cache (company, job_title, COALESCE(location, ''))
                """))
                await conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_salary_cache_lookup
                    ON salary_cache (company, job_title, location)
                """))
                print("  Migration: salary_cache table and indexes ensured")
            else:
                # SQLite: check if table exists first
                result = await conn.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='salary_cache'"
                ))
                if not result.fetchone():
                    await conn.execute(text("""
                        CREATE TABLE salary_cache (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            company VARCHAR(255) NOT NULL,
                            job_title VARCHAR(255) NOT NULL,
                            location VARCHAR(255),
                            median_salary VARCHAR(100),
                            salary_range VARCHAR(200),
                            market_insights TEXT,
                            sources TEXT,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                            UNIQUE (company, job_title, location)
                        )
                    """))
                    print("  Migration: salary_cache table created (SQLite)")
        except Exception as e:
            print(f"  Migration warning (salary_cache): {e}")

        # Ensure mock_interview_sessions table exists
        try:
            if is_postgres:
                await conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS mock_interview_sessions (
                        id SERIAL PRIMARY KEY,
                        interview_prep_id INTEGER NOT NULL REFERENCES interview_preps(id) ON DELETE CASCADE,
                        user_id VARCHAR(255) NOT NULL,
                        interview_type VARCHAR(50) NOT NULL DEFAULT 'behavioral',
                        company VARCHAR(500) NOT NULL,
                        job_title VARCHAR(500) NOT NULL,
                        messages JSONB NOT NULL DEFAULT '[]',
                        performance JSONB,
                        status VARCHAR(20) NOT NULL DEFAULT 'completed',
                        question_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP
                    )
                """))
                await conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_mock_sessions_prep ON mock_interview_sessions(interview_prep_id)
                """))
                await conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_mock_sessions_user ON mock_interview_sessions(user_id)
                """))
                print("  Migration: mock_interview_sessions table and indexes ensured")
            else:
                result = await conn.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='mock_interview_sessions'"
                ))
                if not result.fetchone():
                    await conn.execute(text("""
                        CREATE TABLE mock_interview_sessions (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            interview_prep_id INTEGER NOT NULL REFERENCES interview_preps(id) ON DELETE CASCADE,
                            user_id VARCHAR(255) NOT NULL,
                            interview_type VARCHAR(50) NOT NULL DEFAULT 'behavioral',
                            company VARCHAR(500) NOT NULL,
                            job_title VARCHAR(500) NOT NULL,
                            messages TEXT NOT NULL DEFAULT '[]',
                            performance TEXT,
                            status VARCHAR(20) NOT NULL DEFAULT 'completed',
                            question_count INTEGER DEFAULT 0,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            completed_at DATETIME
                        )
                    """))
                    print("  Migration: mock_interview_sessions table created (SQLite)")
        except Exception as e:
            print(f"  Migration warning (mock_interview_sessions): {e}")

    print("Migrations completed")
