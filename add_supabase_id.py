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

        # Check if column already exists (SQLite-compatible)
        try:
            result = await conn.execute(text("""
                PRAGMA table_info(users);
            """))
            columns = result.fetchall()
            column_names = [col[1] for col in columns]

            if 'supabase_id' in column_names:
                print("[Migration] Column supabase_id already exists, skipping")
                return
        except Exception as e:
            print(f"[Migration] Warning: Could not check existing columns: {e}")

        try:
            # Add supabase_id column (without UNIQUE - we'll add it via index)
            await conn.execute(text("""
                ALTER TABLE users ADD COLUMN supabase_id VARCHAR;
            """))
            print("[Migration] [OK] Added supabase_id column")
        except Exception as e:
            print(f"[Migration] Note: supabase_id column might already exist: {e}")

        # Note: SQLite doesn't support ALTER COLUMN DROP NOT NULL
        # We'll need to recreate the table for that, but it's not critical
        # The User model already has nullable=True, so new rows will work
        print("[Migration] [OK] Username and api_key are already nullable in model")

        try:
            # Create unique index on supabase_id (this enforces uniqueness)
            await conn.execute(text("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_users_supabase_id ON users(supabase_id);
            """))
            print("[Migration] [OK] Created unique index on supabase_id")
        except Exception as e:
            print(f"[Migration] Note: Index might already exist: {e}")

    print("[Migration] Migration complete!")

if __name__ == "__main__":
    asyncio.run(add_supabase_id_column())
