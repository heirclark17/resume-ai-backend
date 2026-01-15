#!/usr/bin/env python3
"""
Simple migration script that works with Railway
"""
import os
import asyncio
import asyncpg

async def run_migration():
    """Execute migration SQL"""

    # Get DATABASE_URL from environment
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        print("ERROR: DATABASE_URL not found in environment")
        return

    # Convert to asyncpg format if needed
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    # Remove any driver suffix like +asyncpg
    database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

    print("=" * 50)
    print("Running database migration: add_session_user_id")
    print("=" * 50)

    # Read SQL migration
    sql_statements = [
        "ALTER TABLE base_resumes ADD COLUMN IF NOT EXISTS session_user_id VARCHAR;",
        "ALTER TABLE tailored_resumes ADD COLUMN IF NOT EXISTS session_user_id VARCHAR;",
        "CREATE INDEX IF NOT EXISTS idx_base_resumes_session_user_id ON base_resumes(session_user_id);",
        "CREATE INDEX IF NOT EXISTS idx_tailored_resumes_session_user_id ON tailored_resumes(session_user_id);"
    ]

    try:
        # Connect to database
        conn = await asyncpg.connect(database_url)
        print("✓ Connected to database")

        # Execute each statement
        for i, sql in enumerate(sql_statements, 1):
            print(f"\nExecuting statement {i}/{len(sql_statements)}...")
            print(f"  SQL: {sql[:60]}...")
            await conn.execute(sql)
            print("  ✓ Success")

        # Verify columns were created
        print("\nVerifying migration...")
        result = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'base_resumes' AND column_name = 'session_user_id'
        """)

        if result:
            print(f"  ✓ base_resumes.session_user_id: {result[0]['data_type']}")
        else:
            print("  ✗ base_resumes.session_user_id: NOT FOUND")

        result = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'tailored_resumes' AND column_name = 'session_user_id'
        """)

        if result:
            print(f"  ✓ tailored_resumes.session_user_id: {result[0]['data_type']}")
        else:
            print("  ✗ tailored_resumes.session_user_id: NOT FOUND")

        await conn.close()

        print("\n" + "=" * 50)
        print("Migration completed successfully!")
        print("=" * 50)
        print("\nSession-based user isolation is now active.")
        print("Each user will only see their own resumes.")

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    asyncio.run(run_migration())
