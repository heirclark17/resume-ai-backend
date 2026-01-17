#!/usr/bin/env python3
"""
Run career plans table migration
"""
import psycopg2
import sys

# Use public Railway URL
database_url = "postgresql://postgres:SUCByvKQvPeSxnLxystaiyRvEMpRvDUn@switchyard.proxy.rlwy.net:54571/railway"

print("=" * 70)
print("Running Career Plans Table Migration")
print("=" * 70)

try:
    print("\n[+] Connecting to database...")
    conn = psycopg2.connect(database_url)
    conn.autocommit = True
    cursor = conn.cursor()

    print("[+] Reading migration file...")
    with open('migrations/add_career_plans_table.sql', 'r') as f:
        migration_sql = f.read()

    print("[+] Executing migration...")

    # Execute the entire migration
    cursor.execute(migration_sql)

    print("\n" + "=" * 70)
    print("[+] Migration completed successfully!")
    print("=" * 70)
    print("\nThe career_plans table is now ready!")
    print("Users can now create AI-generated career transition plans.")

    cursor.close()
    conn.close()

except Exception as e:
    print(f"\n[X] ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
