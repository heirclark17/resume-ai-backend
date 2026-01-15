import psycopg2
import os
import sys

DATABASE_URL = os.environ.get('DATABASE_URL')
print(f"Connecting to database...", file=sys.stderr)

with open('migrations/add_saved_comparisons.sql', 'r') as f:
    migration_sql = f.read()

try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    print("Executing migration...", file=sys.stderr)
    cursor.execute(migration_sql)
    conn.commit()
    
    print("MIGRATION SUCCESS", file=sys.stderr)
    
    cursor.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name IN ('saved_comparisons', 'tailored_resume_edits')
    """)
    tables = [t[0] for t in cursor.fetchall()]
    print(f"Tables created: {tables}", file=sys.stderr)
    
    cursor.close()
    conn.close()
    print("DONE")
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
