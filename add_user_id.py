#!/usr/bin/env python3
"""
Add missing user_id column to base_resumes
"""
import psycopg2

DATABASE_URL = "postgresql://postgres:SUCByvKQvPeSxnLxystaiyRvEMpRvDUn@switchyard.proxy.rlwy.net:54571/railway"

print("=" * 60)
print("  Adding Missing user_id Column")
print("=" * 60)
print()

conn = psycopg2.connect(DATABASE_URL)
conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
cursor = conn.cursor()

print("Adding user_id column to base_resumes...")
try:
    cursor.execute("""
        ALTER TABLE base_resumes
        ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;
    """)
    print("OK - user_id column added successfully!")
except Exception as e:
    print(f"ERROR: {e}")

print()
print("Creating index on user_id...")
try:
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_base_resumes_user_id ON base_resumes(user_id);
    """)
    print("OK - Index created successfully!")
except Exception as e:
    print(f"ERROR: {e}")

cursor.close()
conn.close()

print()
print("=" * 60)
print("  Complete! Testing upload now...")
print("=" * 60)
