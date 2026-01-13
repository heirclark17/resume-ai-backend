#!/usr/bin/env python3
"""
Test tailoring endpoint
"""
import requests

BACKEND_URL = "https://resume-ai-backend-production-3134.up.railway.app"
TAILOR_ENDPOINT = f"{BACKEND_URL}/api/tailor/tailor"

print("=" * 60)
print("  Testing Tailoring Endpoint")
print("=" * 60)
print()

# Test data
payload = {
    "base_resume_id": 22,
    "company": "Test Company",
    "job_title": "Test Job Title",
    "job_description": "This is a test job description for a software engineer position."
}

print(f"Endpoint: {TAILOR_ENDPOINT}")
print(f"Payload: {payload}")
print()

print("Sending POST request...")
try:
    response = requests.post(
        TAILOR_ENDPOINT,
        json=payload,
        timeout=120  # 2 minute timeout for AI processing
    )

    print(f"Response Status: {response.status_code}")
    print()

    if response.status_code == 200:
        print("SUCCESS!")
        data = response.json()
        print(f"Tailored Resume ID: {data.get('id', 'N/A')}")
        print(f"Quality Score: {data.get('quality_score', 'N/A')}")
    else:
        print("FAILED!")
        print(f"Response: {response.text[:500]}")

except requests.exceptions.Timeout:
    print("ERROR: Request timed out (took more than 2 minutes)")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")

print()
print("=" * 60)
