#!/usr/bin/env python3
"""
Migration using public DATABASE_URL
"""
import asyncio
import sys

DATABASE_URL = "postgresql://postgres:SUCByvKQvPeSxnLxystaiyRvEMpRvDUn@switchyard.proxy.rlwy.net:54571/railway"

print("=" * 70)
print("Running Database Migration")
print("=" * 70)
print(f"Connecting to: switchyard.proxy.rlwy.net:54571/railway")

# Import asyncpg
try:
    import asyncpg
except ImportError:
    print("\nInstalling asyncpg...")
    import subprocess
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'asyncpg', '--user'])
    import asyncpg

async def run_migration():
    try:
        print("\nConnecting to database...")
        conn = await asyncpg.connect(DATABASE_URL)
        print("SUCCESS: Connected to database!")

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

        print("\nExecuting migration statements...")
        for desc, sql in statements:
            print(f"\n  {desc}...")
            await conn.execute(sql)
            print(f"    OK Success")

        # Verify
        print("\nVerifying migration...")
        result = await conn.fetch("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_name IN ('base_resumes', 'tailored_resumes')
            AND column_name = 'session_user_id'
            ORDER BY table_name
        """)

        if len(result) == 2:
            print("\n  OK Columns created successfully:")
            for row in result:
                print(f"    - {row['table_name']}.{row['column_name']}: {row['data_type']}")
        else:
            print(f"\n  WARNING Warning: Expected 2 columns, found {len(result)}")

        await conn.close()

        print("\n" + "=" * 70)
        print("OK MIGRATION COMPLETED SUCCESSFULLY!")
        print("=" * 70)
        print("\nNext steps:")
        print("1. Deploy backend code (git push)")
        print("2. Deploy frontend code")
        print("3. Test user isolation in two browsers")
        print("\n" + "=" * 70)

    except Exception as e:
        print(f"\nERROR ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

asyncio.run(run_migration())
