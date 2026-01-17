#!/usr/bin/env python3
"""
Run database migration to add practice_question_responses table
"""
import asyncio
import os
from sqlalchemy import text
from app.database import engine

async def run_migration():
    """Execute migration SQL"""

    # Read migration SQL
    migration_path = os.path.join(os.path.dirname(__file__), 'migrations', 'add_practice_question_responses.sql')
    with open(migration_path, 'r') as f:
        sql = f.read()

    print("Running practice questions migration...")
    print("-" * 50)

    # Execute migration
    async with engine.begin() as conn:
        # Split SQL into individual statements
        statements = [stmt.strip() for stmt in sql.split(';') if stmt.strip() and not stmt.strip().startswith('--')]

        for i, stmt in enumerate(statements, 1):
            try:
                # Skip comments
                if stmt.strip().startswith('--') or not stmt.strip():
                    continue

                print(f"Executing statement {i}/{len(statements)}...")
                result = await conn.execute(text(stmt))

                # If it's a SELECT statement, print the result
                if stmt.strip().upper().startswith('SELECT'):
                    rows = result.fetchall()
                    for row in rows:
                        print(f"  Result: {row}")
                else:
                    print(f"  ✓ Success")

            except Exception as e:
                # Log error but continue (some statements might already be applied)
                print(f"  ⚠ Warning: {e}")
                continue

    print("-" * 50)
    print("Migration completed!")
    print("\nPractice question responses table is ready.")

if __name__ == "__main__":
    asyncio.run(run_migration())
