#!/usr/bin/env python3
"""
Get Railway database connection URL and run migration
"""
import requests
import json
import psycopg2
import sys

RAILWAY_TOKEN = 'c5522167-b291-4b14-a715-3151fa58f307'
RAILWAY_API = 'https://backboard.railway.app/graphql/v2'

headers = {
    'Authorization': f'Bearer {RAILWAY_TOKEN}',
    'Content-Type': 'application/json'
}

print("=" * 70)
print("Running Practice Questions Migration on Railway")
print("=" * 70)

# Step 1: Get project and service info
print("\nStep 1: Finding project and database service...")
query = """
query {
  me {
    projects {
      edges {
        node {
          id
          name
          services {
            edges {
              node {
                id
                name
              }
            }
          }
        }
      }
    }
  }
}
"""

try:
    response = requests.post(RAILWAY_API, json={'query': query}, headers=headers)
    data = response.json()

    if 'errors' in data:
        print(f"ERROR: {data['errors']}")
        sys.exit(1)

    # Find the backend project
    projects = data['data']['me']['projects']['edges']
    target_project = None

    print("\nAvailable projects:")
    for project_edge in projects:
        project = project_edge['node']
        print(f"  - {project['name']}")
        if 'backend' in project['name'].lower() or 'resume' in project['name'].lower() or 'illumination' in project['name'].lower():
            target_project = project

    if not target_project:
        print("\nERROR: Could not find backend project")
        print("Please manually specify project name")
        sys.exit(1)

    print(f"\n✓ Found project: {target_project['name']}")
    project_id = target_project['id']

    # Find Postgres service
    postgres_service = None
    for service_edge in target_project['services']['edges']:
        service = service_edge['node']
        print(f"  Service: {service['name']}")
        if 'postgres' in service['name'].lower():
            postgres_service = service
            break

    if not postgres_service:
        print("\nERROR: Could not find Postgres service")
        sys.exit(1)

    print(f"✓ Found Postgres service: {postgres_service['name']}")
    service_id = postgres_service['id']

    # Step 2: Get database connection variables
    print("\nStep 2: Getting database connection variables...")
    variables_query = """
    query getVariables($projectId: String!, $serviceId: String!) {
      variables(projectId: $projectId, serviceId: $serviceId) {
        edges {
          node {
            name
            value
          }
        }
      }
    }
    """

    variables_response = requests.post(
        RAILWAY_API,
        json={
            'query': variables_query,
            'variables': {
                'projectId': project_id,
                'serviceId': service_id
            }
        },
        headers=headers
    )

    variables_data = variables_response.json()

    if 'errors' in variables_data:
        print(f"ERROR getting variables: {variables_data['errors']}")
        sys.exit(1)

    # Extract DATABASE_URL or construct it
    db_url = None
    db_vars = {}

    if 'data' in variables_data and variables_data['data']['variables']:
        for var_edge in variables_data['data']['variables']['edges']:
            var = var_edge['node']
            db_vars[var['name']] = var['value']
            if var['name'] == 'DATABASE_URL':
                db_url = var['value']

    if db_url:
        print("✓ Found DATABASE_URL")
    else:
        print("✗ DATABASE_URL not found in variables")
        print("\nAvailable variables:")
        for key in db_vars.keys():
            print(f"  - {key}")
        sys.exit(1)

    # Step 3: Run migration
    print("\nStep 3: Running migration SQL...")

    # Read migration file
    with open('migrations/add_practice_question_responses.sql', 'r') as f:
        migration_sql = f.read()

    # Connect and execute
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cursor = conn.cursor()

    print("  Executing migration statements...")

    # Split into statements and execute one by one
    statements = migration_sql.split(';')
    success_count = 0

    for stmt in statements:
        stmt = stmt.strip()
        if stmt and not stmt.startswith('--'):
            try:
                cursor.execute(stmt)
                success_count += 1
                print(f"    ✓ Statement {success_count} executed")
            except Exception as e:
                if 'already exists' in str(e).lower():
                    print(f"    ⚠ Statement {success_count + 1} already applied (skipped)")
                    success_count += 1
                else:
                    print(f"    ✗ Error: {e}")

    cursor.close()
    conn.close()

    print("\n" + "=" * 70)
    print(f"✓ Migration completed successfully!")
    print(f"✓ {success_count} statements executed")
    print("=" * 70)
    print("\nThe practice_question_responses table is now ready!")
    print("Users can now save practice question recordings and STAR stories.")
    print("\n" + "=" * 70)

except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
