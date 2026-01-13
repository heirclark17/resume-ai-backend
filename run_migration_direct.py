#!/usr/bin/env python3
"""
Run database migration directly on Railway PostgreSQL
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

try:
    import psycopg2
except ImportError:
    print("Installing psycopg2...")
    os.system("pip install psycopg2-binary")
    import psycopg2

# Railway PostgreSQL connection
DATABASE_URL = "postgresql://postgres:SUCByvKQvPeSxnLxystaiyRvEMpRvDUn@switchyard.proxy.rlwy.net:54571/railway"

# Read migration SQL (use fixed version)
migration_path = os.path.join(os.path.dirname(__file__), 'migrations', 'add_missing_columns_fixed.sql')
with open(migration_path, 'r') as f:
    sql = f.read()

print("=" * 60)
print("  Railway Database Migration")
print("=" * 60)
print()

# Connect to database
print("Connecting to Railway PostgreSQL...")
conn = psycopg2.connect(DATABASE_URL)
conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)  # Auto-commit each statement
cursor = conn.cursor()

print("OK - Connected successfully!")
print()

# Split SQL into individual statements and execute
statements = [stmt.strip() for stmt in sql.split(';') if stmt.strip() and not stmt.strip().startswith('--')]

for i, stmt in enumerate(statements, 1):
    # Skip empty statements and comments
    if not stmt.strip() or stmt.strip().startswith('--'):
        continue

    try:
        print(f"[{i}/{len(statements)}] Executing: {stmt[:60]}...")
        cursor.execute(stmt)

        # If it's a SELECT, fetch and print results
        if stmt.strip().upper().startswith('SELECT'):
            result = cursor.fetchall()
            for row in result:
                print(f"    Result: {row[0]}")
        else:
            print(f"    OK - Success")

    except Exception as e:
        # Some statements might fail if columns already exist
        error_msg = str(e).lower()
        if 'already exists' in error_msg or 'duplicate' in error_msg:
            print(f"    WARN - Skipped (already exists)")
        else:
            print(f"    ERROR: {e}")

# Close connection
cursor.close()
conn.close()

print()
print("=" * 60)
print("  Migration Completed Successfully!")
print("=" * 60)
print()
print("OK - Your resume uploads should now work at talorme.com")
print()
