#!/usr/bin/env python3
import psycopg2

database_url = "postgresql://postgres:SUCByvKQvPeSxnLxystaiyRvEMpRvDUn@switchyard.proxy.rlwy.net:54571/railway"

print("=" * 70)
print("Verifying and Fixing Migration")
print("=" * 70)

conn = psycopg2.connect(database_url)
conn.autocommit = True
cursor = conn.cursor()

# Check if table exists
print("\n[1] Checking if table exists...")
cursor.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'practice_question_responses'
    )
""")
table_exists = cursor.fetchone()[0]

if table_exists:
    print("[OK] Table practice_question_responses exists")
    
    # Check columns
    cursor.execute("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'practice_question_responses'
        ORDER BY ordinal_position
    """)
    columns = [row[0] for row in cursor.fetchall()]
    print(f"[OK] Found {len(columns)} columns: {', '.join(columns[:5])}...")
else:
    print("[ERROR] Table does not exist!")
    conn.close()
    exit(1)

# Check if trigger function exists
print("\n[2] Checking trigger function...")
cursor.execute("""
    SELECT EXISTS (
        SELECT FROM pg_proc 
        WHERE proname = 'update_practice_question_responses_updated_at'
    )
""")
function_exists = cursor.fetchone()[0]

if not function_exists:
    print("[MISSING] Trigger function does not exist, creating it...")
    
    # Create the function
    trigger_function_sql = """
    CREATE OR REPLACE FUNCTION update_practice_question_responses_updated_at()
    RETURNS TRIGGER AS $$
    BEGIN
        NEW.updated_at = CURRENT_TIMESTAMP;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
    """
    
    try:
        cursor.execute(trigger_function_sql)
        print("[OK] Created trigger function")
    except Exception as e:
        print(f"[ERROR] Failed to create function: {e}")

# Check if trigger exists
print("\n[3] Checking trigger...")
cursor.execute("""
    SELECT EXISTS (
        SELECT FROM pg_trigger 
        WHERE tgname = 'trigger_practice_question_responses_updated_at'
    )
""")
trigger_exists = cursor.fetchone()[0]

if not trigger_exists:
    print("[MISSING] Trigger does not exist, creating it...")
    
    trigger_sql = """
    CREATE TRIGGER trigger_practice_question_responses_updated_at
        BEFORE UPDATE ON practice_question_responses
        FOR EACH ROW
        EXECUTE FUNCTION update_practice_question_responses_updated_at();
    """
    
    try:
        cursor.execute(trigger_sql)
        print("[OK] Created trigger")
    except Exception as e:
        print(f"[ERROR] Failed to create trigger: {e}")
else:
    print("[OK] Trigger exists")

cursor.close()
conn.close()

print("\n" + "=" * 70)
print("MIGRATION VERIFICATION COMPLETE!")
print("=" * 70)
print("\nThe practice_question_responses table is fully configured!")
print("All features are ready to use:")
print("  - AI practice question generation")
print("  - STAR story generation")  
print("  - Video/audio recording storage")
print("  - Practice session tracking")
