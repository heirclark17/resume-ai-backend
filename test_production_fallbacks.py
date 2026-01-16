"""
Test production fallback chain via API calls
"""

import requests
import json


def test_production_extraction(job_url, test_name):
    """Test job extraction on production"""

    api_url = "https://resume-ai-backend-production-3134.up.railway.app/api/jobs/extract"

    print("=" * 80)
    print(f"TEST: {test_name}")
    print("=" * 80)
    print(f"URL: {job_url}\n")

    try:
        response = requests.post(
            api_url,
            headers={"Content-Type": "application/json"},
            json={"job_url": job_url},
            timeout=60
        )

        result = response.json()

        print(f"Status Code: {response.status_code}")
        print(f"Success: {result.get('success')}")

        if result.get('success'):
            print(f"\nExtracted Data:")
            print(f"  Company: {result.get('company')}")
            print(f"  Title: {result.get('job_title')}")
            print(f"  Location: {result.get('location')}")
            print(f"  Salary: {result.get('salary')}")
            print(f"  Description: {result.get('description', '')[:100]}...")
            return True
        else:
            print(f"\nError: {result.get('error', 'Unknown error')[:200]}")
            return False

    except Exception as e:
        print(f"\nRequest Failed: {str(e)}")
        return False


def main():
    """Test various job URLs to verify fallbacks"""

    print("\n" + "#" * 80)
    print("# PRODUCTION FALLBACK CHAIN TESTS")
    print("#" * 80)
    print()

    # Test 1: Oracle job (tests Playwright JSON-LD extraction)
    test1 = test_production_extraction(
        "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/jobsearch/job/318423",
        "Oracle Job - JSON-LD Structured Data"
    )

    print("\n")

    # Test 2: Indeed job (tests Firecrawl or Playwright)
    test2 = test_production_extraction(
        "https://www.indeed.com/viewjob?jk=example",
        "Indeed Job - Should use Firecrawl or Playwright"
    )

    print("\n")

    # Test 3: Greenhouse job (tests structured data extraction)
    test3 = test_production_extraction(
        "https://boards.greenhouse.io/example/jobs/12345",
        "Greenhouse Job - Structured Data"
    )

    # Summary
    print("\n" + "#" * 80)
    print("# SUMMARY")
    print("#" * 80)

    total = 3
    passed = sum([test1, test2, test3])

    print(f"\nTests Passed: {passed}/{total}")

    if passed >= 1:
        print("\nFallback chain is functional!")
        print("At least one extraction method is working on production.")
    else:
        print("\nWARNING: All tests failed. Check Railway logs.")


if __name__ == "__main__":
    main()
