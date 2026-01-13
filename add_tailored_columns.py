#!/usr/bin/env python3
"""
Add missing soft delete columns to tailored_resumes table
"""
import psycopg2

DATABASE_URL = "postgresql://postgres:SUCByvKQvPeSxnLxystaiyRvEMpRvDUn@switchyard.proxy.rlwy.net:54571/railway"

print("=" * 60)
print("  Adding Soft Delete Columns to tailored_resumes")
print("=" * 60)
print()

conn = psycopg2.connect(DATABASE_URL)
conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
cursor = conn.cursor()

print("Adding columns to tailored_resumes table...")
print()

columns_to_add = [
    ("is_deleted", "BOOLEAN DEFAULT FALSE"),
    ("deleted_at", "TIMESTAMP"),
    ("deleted_by", "INTEGER REFERENCES users(id) ON DELETE SET NULL"),
]

for col_name, col_type in columns_to_add:
    try:
        sql = f"ALTER TABLE tailored_resumes ADD COLUMN IF NOT EXISTS {col_name} {col_type};"
        cursor.execute(sql)
        print(f"OK - {col_name}")
    except Exception as e:
        print(f"ERROR - {col_name}: {e}")

print()
print("Creating indexes...")
print()

indexes = [
    "CREATE INDEX IF NOT EXISTS idx_tailored_resumes_is_deleted ON tailored_resumes(is_deleted);",
    "CREATE INDEX IF NOT EXISTS idx_tailored_resumes_deleted_at ON tailored_resumes(deleted_at);",
]

for idx_sql in indexes:
    try:
        cursor.execute(idx_sql)
        print(f"OK - Created index")
    except Exception as e:
        print(f"ERROR: {e}")

cursor.close()
conn.close()

print()
print("=" * 60)
print("  Complete!")
print("=" * 60)
