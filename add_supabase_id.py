#!/usr/bin/env python3
"""
Database migration: Add supabase_id column to users table
"""

import asyncio
from app.database import engine, Base
from sqlalchemy import text

async def add_supabase_id_column():
    """Add supabase_id column to users table"""

    async with engine.begin() as conn:
        print("[Migration] Adding supabase_id column to users table...")

        # Check if column already exists
        result = await conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'users'
            AND column_name = 'supabase_id';
        """))

        if result.fetchone():
            print("[Migration] Column supabase_id already exists, skipping")
            return

        # Add supabase_id column
        await conn.execute(text("""
            ALTER TABLE users
            ADD COLUMN supabase_id VARCHAR UNIQUE;
        """))

        print("[Migration] ✓ Added supabase_id column")

        # Make username nullable (for Supabase users)
        await conn.execute(text("""
            ALTER TABLE users
            ALTER COLUMN username DROP NOT NULL;
        """))

        print("[Migration] ✓ Made username nullable")

        # Make api_key nullable (for Supabase users)
        await conn.execute(text("""
            ALTER TABLE users
            ALTER COLUMN api_key DROP NOT NULL;
        """))

        print("[Migration] ✓ Made api_key nullable")

        # Create index on supabase_id
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_users_supabase_id
            ON users(supabase_id);
        """))

        print("[Migration] ✓ Created index on supabase_id")

    print("[Migration] Migration complete!")

if __name__ == "__main__":
    asyncio.run(add_supabase_id_column())
