#!/usr/bin/env python3
"""
Run practice questions migration using Railway API
"""
import os
import subprocess
import sys

# Set Railway token from user
os.environ['RAILWAY_TOKEN'] = 'c5522167-b291-4b14-a715-3151fa58f307'

# Read migration SQL
migration_file = 'migrations/add_practice_question_responses.sql'
with open(migration_file, 'r') as f:
    sql = f.read()

# Save to temp file
sql_file = 'temp_practice_questions_migration.sql'
with open(sql_file, 'w') as f:
    f.write(sql)

print("=" * 70)
print("Running Practice Questions Migration on Railway")
print("=" * 70)

try:
    # Change to backend directory
    os.chdir(r'C:\Users\derri\projects\resume-ai-app\backend')

    # Use railway shell to execute SQL
    result = subprocess.run(
        ['railway', 'run', '--service', 'Postgres', 'psql', '-f', sql_file],
        capture_output=True,
        text=True,
        timeout=120
    )

    print("\nSTDOUT:")
    print(result.stdout)

    if result.stderr:
        print("\nSTDERR:")
        print(result.stderr)

    if result.returncode == 0:
        print("\n" + "=" * 70)
        print("✓ Practice Questions Migration completed successfully!")
        print("✓ practice_question_responses table created")
        print("✓ Indexes created")
        print("✓ Triggers created")
        print("=" * 70)
    else:
        print("\n" + "=" * 70)
        print(f"✗ Migration failed with exit code {result.returncode}")
        print("=" * 70)
        sys.exit(1)

except Exception as e:
    print(f"\n✗ ERROR: {e}")
    sys.exit(1)
finally:
    # Cleanup
    if os.path.exists(sql_file):
        os.remove(sql_file)
