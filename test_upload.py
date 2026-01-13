#!/usr/bin/env python3
"""
Test resume upload to talorme.com backend
"""
import sys
import os
import requests

# Test file - use the PDF that was in the logs
TEST_FILE = r"C:\Users\derri\Downloads\Justin Washington Resume-IT_PM.pdf"
BACKEND_URL = "https://resume-ai-backend-production-3134.up.railway.app"
UPLOAD_ENDPOINT = f"{BACKEND_URL}/api/resumes/upload"

print("=" * 60)
print("  Testing Resume Upload to talorme.com")
print("=" * 60)
print()

# Check if test file exists
if not os.path.exists(TEST_FILE):
    print(f"ERROR: Test file not found: {TEST_FILE}")
    print("Please update TEST_FILE path in the script")
    sys.exit(1)

print(f"Test file: {TEST_FILE}")
print(f"File size: {os.path.getsize(TEST_FILE)} bytes")
print(f"Backend URL: {BACKEND_URL}")
print()

print("Uploading resume...")
print()

try:
    # Open and upload the file
    with open(TEST_FILE, 'rb') as f:
        files = {'file': (os.path.basename(TEST_FILE), f, 'application/pdf')}

        response = requests.post(
            UPLOAD_ENDPOINT,
            files=files,
            timeout=60  # 60 second timeout for AI parsing
        )

    print(f"Response Status: {response.status_code}")
    print()

    if response.status_code == 200:
        data = response.json()
        print("=" * 60)
        print("  SUCCESS! Upload worked!")
        print("=" * 60)
        print()
        print(f"Resume ID: {data.get('resume_id')}")
        print(f"Filename: {data.get('filename')}")
        print()

        parsed = data.get('parsed_data', {})
        print(f"Candidate Name: {parsed.get('candidate_name', 'N/A')}")
        print(f"Candidate Email: {parsed.get('candidate_email', 'N/A')}")
        print(f"Skills Found: {len(parsed.get('skills', []))} skills")
        print(f"Jobs Found: {len(parsed.get('experience', []))} jobs")
        print()

        if 'warnings' in data:
            print("Warnings:")
            for warning in data['warnings']:
                print(f"  - {warning}")

        print()
        print("The upload is now working correctly on talorme.com!")

    else:
        print("=" * 60)
        print("  FAILED - Error occurred")
        print("=" * 60)
        print()
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text[:500]}")

except requests.exceptions.Timeout:
    print("ERROR: Request timed out (took more than 60 seconds)")
    print("This might indicate the AI parsing is slow")

except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 60)
