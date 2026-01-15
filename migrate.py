#!/usr/bin/env python3
"""
Simple migration script that runs inside Railway environment
"""
import os
import sys

# This script will be run via: railway run python migrate.py
# So it will have access to DATABASE_URL environment variable

database_url = os.getenv("DATABASE_URL")

if not database_url:
    print("ERROR: DATABASE_URL not found")
    sys.exit(1)

print("=" * 70)
print("Running Database Migration")
print("=" * 70)
print(f"Database: {database_url.split('@')[1] if '@' in database_url else 'unknown'}")

# Import after confirming environment
try:
    import asyncpg
except ImportError:
    print("\nInstalling asyncpg...")
    import subprocess
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'asyncpg'])
    import asyncpg

import asyncio

async def run_migration():
    # Convert URL format if needed
    url = database_url
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    print("\nConnecting to database...")

    try:
        conn = await asyncpg.connect(url)
        print("Connected successfully!")

        # Run migration SQL
        statements = [
            ("Adding session_user_id to base_resumes",
             "ALTER TABLE base_resumes ADD COLUMN IF NOT EXISTS session_user_id VARCHAR"),

            ("Adding session_user_id to tailored_resumes",
             "ALTER TABLE tailored_resumes ADD COLUMN IF NOT EXISTS session_user_id VARCHAR"),

            ("Creating index on base_resumes",
             "CREATE INDEX IF NOT EXISTS idx_base_resumes_session_user_id ON base_resumes(session_user_id)"),

            ("Creating index on tailored_resumes",
             "CREATE INDEX IF NOT EXISTS idx_tailored_resumes_session_user_id ON tailored_resumes(session_user_id)"),
        ]

        for desc, sql in statements:
            print(f"\n{desc}...")
            await conn.execute(sql)
            print("  Success!")

        # Verify
        print("\nVerifying migration...")
        result = await conn.fetch("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_name IN ('base_resumes', 'tailored_resumes')
            AND column_name = 'session_user_id'
            ORDER BY table_name
        """)

        for row in result:
            print(f"  {row['table_name']}.{row['column_name']}: {row['data_type']}")

        await conn.close()

        print("\n" + "=" * 70)
        print("Migration Completed Successfully!")
        print("=" * 70)
        print("\nNext steps:")
        print("1. Deploy backend code: git push")
        print("2. Deploy frontend code")
        print("3. Test user isolation")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

asyncio.run(run_migration())
