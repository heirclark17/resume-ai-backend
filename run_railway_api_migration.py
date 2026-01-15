#!/usr/bin/env python3
"""
Run migration using Railway GraphQL API
"""
import requests
import json

RAILWAY_TOKEN = '74fbb833-6940-4ca5-aa5f-5453195e251e'
RAILWAY_API = 'https://backboard.railway.app/graphql/v2'

headers = {
    'Authorization': f'Bearer {RAILWAY_TOKEN}',
    'Content-Type': 'application/json'
}

print("=" * 70)
print("Railway Database Migration via API")
print("=" * 70)

# Step 1: Get project info
print("\nStep 1: Getting project information...")
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

response = requests.post(RAILWAY_API, json={'query': query}, headers=headers)
data = response.json()

if 'errors' in data:
    print(f"ERROR: {data['errors']}")
    exit(1)

# Find the distinguished-illumination project
projects = data['data']['me']['projects']['edges']
target_project = None

for project_edge in projects:
    project = project_edge['node']
    if project['name'] == 'distinguished-illumination':
        target_project = project
        break

if not target_project:
    print("ERROR: Could not find 'distinguished-illumination' project")
    print("\nAvailable projects:")
    for project_edge in projects:
        print(f"  - {project_edge['node']['name']}")
    exit(1)

print(f"  Found project: {target_project['name']}")
print(f"  Project ID: {target_project['id']}")

# Find Postgres service
postgres_service = None
for service_edge in target_project['services']['edges']:
    service = service_edge['node']
    if 'postgres' in service['name'].lower() or service['name'] == 'Postgres':
        postgres_service = service
        break

if not postgres_service:
    print("ERROR: Could not find Postgres service")
    exit(1)

print(f"  Found service: {postgres_service['name']}")
print(f"  Service ID: {postgres_service['id']}")

print("\n" + "=" * 70)
print("INSTRUCTIONS TO COMPLETE MIGRATION")
print("=" * 70)
print("\nI cannot directly execute SQL via Railway's API.")
print("However, I've confirmed your project and database exist.")
print("\nPlease run this SQL in Railway Dashboard:")
print("\n1. Go to: https://railway.app/project/" + target_project['id'])
print("2. Click on 'Postgres' service")
print("3. Click 'Query' tab")
print("4. Copy/paste this SQL:")
print("\n" + "-" * 70)

sql = """-- Add session_user_id columns
ALTER TABLE base_resumes ADD COLUMN IF NOT EXISTS session_user_id VARCHAR;
ALTER TABLE tailored_resumes ADD COLUMN IF NOT EXISTS session_user_id VARCHAR;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_base_resumes_session_user_id ON base_resumes(session_user_id);
CREATE INDEX IF NOT EXISTS idx_tailored_resumes_session_user_id ON tailored_resumes(session_user_id);

-- Verify
SELECT 'base_resumes' as table_name, column_name, data_type
FROM information_schema.columns
WHERE table_name = 'base_resumes' AND column_name = 'session_user_id'
UNION ALL
SELECT 'tailored_resumes' as table_name, column_name, data_type
FROM information_schema.columns
WHERE table_name = 'tailored_resumes' AND column_name = 'session_user_id';"""

print(sql)
print("-" * 70)
print("\n5. Click 'Execute'")
print("\n6. You should see output confirming the columns were created")
print("\n" + "=" * 70)
