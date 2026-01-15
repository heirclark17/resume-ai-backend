#!/usr/bin/env python3
"""
Run migration using Railway API token
"""
import os
import subprocess
import sys

# Set Railway token
os.environ['RAILWAY_TOKEN'] = '74fbb833-6940-4ca5-aa5f-5453195e251e'

# SQL migration
sql = """
-- Add session_user_id columns
ALTER TABLE base_resumes ADD COLUMN IF NOT EXISTS session_user_id VARCHAR;
ALTER TABLE tailored_resumes ADD COLUMN IF NOT EXISTS session_user_id VARCHAR;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_base_resumes_session_user_id ON base_resumes(session_user_id);
CREATE INDEX IF NOT EXISTS idx_tailored_resumes_session_user_id ON tailored_resumes(session_user_id);

-- Verify
SELECT 'Migration completed successfully!' as status;
"""

# Save SQL to temp file
sql_file = 'temp_migration.sql'
with open(sql_file, 'w') as f:
    f.write(sql)

print("=" * 70)
print("Running Railway Database Migration")
print("=" * 70)

try:
    # Execute SQL via Railway
    # Change to backend directory first
    os.chdir(r'C:\Users\derri\projects\resume-ai-app\backend')

    # Use railway shell to execute SQL
    result = subprocess.run(
        ['railway', 'run', '--service', 'Postgres', 'psql', '-f', sql_file],
        capture_output=True,
        text=True,
        timeout=60
    )

    print("\nSTDOUT:")
    print(result.stdout)

    if result.stderr:
        print("\nSTDERR:")
        print(result.stderr)

    if result.returncode == 0:
        print("\n" + "=" * 70)
        print("✓ Migration completed successfully!")
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
