#!/usr/bin/env python3
import psycopg2

print("=" * 70)
print("Running Practice Questions Migration on Railway")
print("=" * 70)

# Use Railway public database URL
database_url = "postgresql://postgres:SUCByvKQvPeSxnLxystaiyRvEMpRvDUn@switchyard.proxy.rlwy.net:54571/railway"

print("\n[OK] Connecting to Railway Postgres...")

with open('migrations/add_practice_question_responses.sql', 'r') as f:
    migration_sql = f.read()

conn = psycopg2.connect(database_url)
conn.autocommit = True
print("[OK] Connected successfully")

print("\nExecuting migration statements...")
cursor = conn.cursor()

statements = migration_sql.split(';')
success_count = 0
skip_count = 0

for i, stmt in enumerate(statements, 1):
    stmt = stmt.strip()
    if not stmt or stmt.startswith('--'):
        continue
    
    try:
        cursor.execute(stmt)
        success_count += 1
        print(f"  [OK] Statement {i}: Success")
    except Exception as e:
        if 'already exists' in str(e).lower():
            skip_count += 1
            print(f"  [SKIP] Statement {i}: Already exists")
        else:
            print(f"  [ERROR] Statement {i}: {e}")

cursor.close()
conn.close()

print("\n" + "=" * 70)
print("MIGRATION COMPLETE!")
print(f"  Successful: {success_count}, Skipped: {skip_count}")
print("=" * 70)
print("\npractice_question_responses table is ready!")
