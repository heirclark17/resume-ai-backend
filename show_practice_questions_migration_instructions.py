#!/usr/bin/env python3
"""
Show instructions for running practice questions migration on Railway
"""
import requests
import json

RAILWAY_TOKEN = 'c5522167-b291-4b14-a715-3151fa58f307'
RAILWAY_API = 'https://backboard.railway.app/graphql/v2'

headers = {
    'Authorization': f'Bearer {RAILWAY_TOKEN}',
    'Content-Type': 'application/json'
}

print("=" * 70)
print("Practice Questions Migration for Railway")
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

try:
    response = requests.post(RAILWAY_API, json={'query': query}, headers=headers)
    data = response.json()

    if 'errors' in data:
        print(f"ERROR: {data['errors']}")
        print("\nFalling back to direct migration SQL instructions...")
        project_found = False
    else:
        # Find project
        projects = data['data']['me']['projects']['edges']
        target_project = None

        for project_edge in projects:
            project = project_edge['node']
            if 'backend' in project['name'].lower() or 'resume' in project['name'].lower():
                target_project = project
                break

        if target_project:
            print(f"  Found project: {target_project['name']}")
            print(f"  Project ID: {target_project['id']}")

            # Find Postgres service
            postgres_service = None
            for service_edge in target_project['services']['edges']:
                service = service_edge['node']
                if 'postgres' in service['name'].lower():
                    postgres_service = service
                    break

            if postgres_service:
                print(f"  Found service: {postgres_service['name']}")
                project_found = True
                project_url = f"https://railway.app/project/{target_project['id']}"
            else:
                project_found = False
        else:
            print("\nAvailable projects:")
            for project_edge in projects:
                print(f"  - {project_edge['node']['name']}")
            project_found = False

except Exception as e:
    print(f"  Warning: Could not fetch project info: {e}")
    project_found = False

# Read migration SQL
print("\n" + "=" * 70)
print("MIGRATION SQL TO RUN")
print("=" * 70)

with open('migrations/add_practice_question_responses.sql', 'r') as f:
    sql = f.read()

print("\nCopy and paste this SQL into Railway Dashboard:\n")
if project_found:
    print(f"1. Go to: {project_url}")
    print("2. Click on 'Postgres' service")
    print("3. Click 'Query' tab")
    print("4. Copy/paste this SQL:\n")
else:
    print("1. Go to: https://railway.app")
    print("2. Select your backend project")
    print("3. Click on 'Postgres' service")
    print("4. Click 'Query' tab")
    print("5. Copy/paste this SQL:\n")

print("-" * 70)
print(sql)
print("-" * 70)

print("\n6. Click 'Execute'")
print("\n7. You should see confirmation that the table was created")
print("\n" + "=" * 70)
print("After running this migration, the practice questions feature will work!")
print("=" * 70)
