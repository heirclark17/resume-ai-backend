#!/usr/bin/env python3
"""Add supabase_id column to users table"""
import asyncio
import asyncpg

async def run_migration():
    # Connect to Railway PostgreSQL
    conn = await asyncpg.connect(
        host='switchyard.proxy.rlwy.net',
        port=54571,
        user='postgres',
        password='SUCByvKQvPeSxnLxystaiyRvEMpRvDUn',
        database='railway'
    )

    try:
        print("Connected to database successfully")

        # Add supabase_id column
        print("Adding supabase_id column...")
        await conn.execute("""
            ALTER TABLE users ADD COLUMN IF NOT EXISTS supabase_id VARCHAR;
        """)
        print("SUCCESS: Column added")

        # Create unique index
        print("Creating unique index...")
        await conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS ix_users_supabase_id ON users(supabase_id);
        """)
        print("SUCCESS: Index created")

        # Verify column exists
        result = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'supabase_id';
        """)

        if result:
            print(f"SUCCESS: Migration complete! Column: {result[0]['column_name']} ({result[0]['data_type']})")
        else:
            print("ERROR: Column not found after migration")

    finally:
        await conn.close()
        print("Database connection closed")

if __name__ == "__main__":
    asyncio.run(run_migration())
