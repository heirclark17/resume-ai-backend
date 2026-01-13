#!/usr/bin/env python3
"""
Add ALL missing columns to match the BaseResume model
"""
import psycopg2

DATABASE_URL = "postgresql://postgres:SUCByvKQvPeSxnLxystaiyRvEMpRvDUn@switchyard.proxy.rlwy.net:54571/railway"

print("=" * 60)
print("  Adding All Missing Columns")
print("=" * 60)
print()

conn = psycopg2.connect(DATABASE_URL)
conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
cursor = conn.cursor()

# List of all columns that should exist
columns_to_add = [
    ("user_id", "INTEGER REFERENCES users(id) ON DELETE CASCADE"),
    ("candidate_name", "VARCHAR"),
    ("candidate_email", "VARCHAR"),
    ("candidate_phone", "VARCHAR"),
    ("candidate_location", "VARCHAR"),
    ("candidate_linkedin", "VARCHAR"),
    ("file_signature", "VARCHAR"),
    ("is_deleted", "BOOLEAN DEFAULT FALSE"),
    ("deleted_at", "TIMESTAMP"),
    ("deleted_by", "INTEGER REFERENCES users(id) ON DELETE SET NULL"),
]

print("Adding missing columns to base_resumes table...")
print()

for col_name, col_type in columns_to_add:
    try:
        sql = f"ALTER TABLE base_resumes ADD COLUMN IF NOT EXISTS {col_name} {col_type};"
        cursor.execute(sql)
        print(f"OK - {col_name}")
    except Exception as e:
        print(f"SKIP - {col_name}: {e}")

print()
print("Creating indexes...")
print()

indexes = [
    "CREATE INDEX IF NOT EXISTS idx_base_resumes_user_id ON base_resumes(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_base_resumes_is_deleted ON base_resumes(is_deleted);",
    "CREATE INDEX IF NOT EXISTS idx_base_resumes_uploaded_at ON base_resumes(uploaded_at);",
]

for idx_sql in indexes:
    try:
        cursor.execute(idx_sql)
        idx_name = idx_sql.split("idx_")[1].split(" ")[0]
        print(f"OK - idx_{idx_name}")
    except Exception as e:
        print(f"SKIP - {e}")

cursor.close()
conn.close()

print()
print("=" * 60)
print("  All columns added!")
print("=" * 60)
