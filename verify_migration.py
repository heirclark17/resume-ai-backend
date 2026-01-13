#!/usr/bin/env python3
"""
Verify database migration columns exist
"""
import psycopg2

# Use the public URL to check
DATABASE_URL = "postgresql://postgres:SUCByvKQvPeSxnLxystaiyRvEMpRvDUn@switchyard.proxy.rlwy.net:54571/railway"

print("=" * 60)
print("  Verifying Database Migration")
print("=" * 60)
print()

# Connect and check columns
conn = psycopg2.connect(DATABASE_URL)
conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
cursor = conn.cursor()

print("Checking base_resumes table columns...")
cursor.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_name = 'base_resumes'
    ORDER BY ordinal_position;
""")

columns = cursor.fetchall()
print(f"\nFound {len(columns)} columns:")
for col_name, col_type in columns:
    print(f"  - {col_name}: {col_type}")

# Check specifically for the new columns
required_columns = ['user_id', 'file_signature', 'is_deleted', 'deleted_at', 'deleted_by']
existing_columns = [col[0] for col in columns]

print("\nRequired columns status:")
for col in required_columns:
    status = "OK" if col in existing_columns else "MISSING"
    print(f"  - {col}: {status}")

cursor.close()
conn.close()

print()
print("=" * 60)
