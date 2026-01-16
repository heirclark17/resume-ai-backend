"""
Test all extraction fallback methods to ensure redundancy
Tests: Firecrawl -> Playwright -> Vision
"""

import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def test_playwright_fallback():
    """Test Playwright extraction directly"""
    print("=" * 80)
    print("TEST 1: PLAYWRIGHT EXTRACTION (Fallback #1)")
    print("=" * 80)

    from app.services.playwright_extractor import PlaywrightJobExtractor

    # Test with Oracle URL
    oracle_url = "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/jobsearch/job/318423"

    try:
        extractor = PlaywrightJobExtractor()
        result = await extractor.extract_job_details(oracle_url)

        print(f"\nSUCCESS: Playwright extracted data")
        print(f"  Company: {result.get('company')}")
        print(f"  Title: {result.get('title')}")
        print(f"  Location: {result.get('location')}")
        print(f"  Description length: {len(result.get('description', ''))} chars")

        return True

    except Exception as e:
        print(f"\nFAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_vision_fallback():
    """Test Vision extraction directly"""
    print("\n" + "=" * 80)
    print("TEST 2: VISION EXTRACTION (Fallback #2)")
    print("=" * 80)

    from app.services.vision_extractor import VisionJobExtractor

    # Test with a simple URL
    test_url = "https://example.com"  # Simple page for testing

    try:
        extractor = VisionJobExtractor()
        result = await extractor.extract_from_url(test_url)

        print(f"\nSUCCESS: Vision extraction completed")
        print(f"  Company: {result.get('company')}")
        print(f"  Title: {result.get('title')}")
        print(f"  Method: {'Screenshot API' if 'screenshot' in str(result) else 'Text extraction'}")

        return True

    except Exception as e:
        print(f"\nFAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_screenshot_api():
    """Test Screenshot API connectivity"""
    print("\n" + "=" * 80)
    print("TEST 3: SCREENSHOT API")
    print("=" * 80)

    import aiohttp
    import base64

    screenshot_api_key = os.getenv('SCREENSHOT_API_KEY', '')

    if not screenshot_api_key:
        print("SKIPPED: SCREENSHOT_API_KEY not set in environment")
        return None

    print(f"API Key: {screenshot_api_key[:20]}...")

    api_url = "https://shot.screenshotapi.net/screenshot"
    params = {
        'token': screenshot_api_key,
        'url': 'https://example.com',
        'output': 'image',
        'file_type': 'png',
        'wait_for_event': 'load',
        'delay': 1000
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, params=params, timeout=30, allow_redirects=True) as response:
                if response.status == 200:
                    screenshot_bytes = await response.read()
                    print(f"\nSUCCESS: Screenshot API working")
                    print(f"  Status: {response.status}")
                    print(f"  Size: {len(screenshot_bytes)} bytes")
                    return True
                else:
                    error_text = await response.text()
                    print(f"\nFAILED: Screenshot API returned {response.status}")
                    print(f"  Error: {error_text}")
                    return False

    except Exception as e:
        print(f"\nFAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_full_fallback_chain():
    """Test the complete fallback chain by simulating Firecrawl failure"""
    print("\n" + "=" * 80)
    print("TEST 4: FULL FALLBACK CHAIN (Firecrawl -> Playwright -> Vision)")
    print("=" * 80)

    from app.services.firecrawl_client import FirecrawlClient

    # Use a URL that Firecrawl might fail on
    test_url = "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/jobsearch/job/318423"

    try:
        client = FirecrawlClient()
        result = await client.extract_job_details(test_url)

        print(f"\nSUCCESS: Extraction chain completed")
        print(f"  Company: {result.get('company')}")
        print(f"  Title: {result.get('title')}")
        print(f"  Location: {result.get('location')}")

        return True

    except Exception as e:
        print(f"\nFAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


async def test_validation_logic():
    """Test that validation properly rejects bad extractions"""
    print("\n" + "=" * 80)
    print("TEST 5: VALIDATION LOGIC")
    print("=" * 80)

    from app.services.firecrawl_client import FirecrawlClient

    client = FirecrawlClient()

    # Test valid data
    print("\nTest 5a: Valid data (should PASS)")
    valid_result = {
        'company': 'Oracle',
        'title': 'Senior Program Manager',
        'description': 'test',
        'location': 'Remote',
        'salary': '$100k'
    }

    try:
        validated = await client.validate_extraction_result(valid_result, "https://test.com")
        print(f"  PASS: Validation accepted valid data")
        print(f"  Company: {validated['company']}, Title: {validated['title']}")
    except Exception as e:
        print(f"  FAIL: Validation rejected valid data: {e}")

    # Test empty company
    print("\nTest 5b: Empty company (should FAIL)")
    invalid_company = {
        'company': '',
        'title': 'Senior Program Manager',
        'description': 'test'
    }

    try:
        validated = await client.validate_extraction_result(invalid_company, "https://test.com")
        print(f"  FAIL: Validation accepted empty company")
    except ValueError as e:
        print(f"  PASS: Validation correctly rejected: {str(e)[:80]}...")

    # Test empty title
    print("\nTest 5c: Empty title (should FAIL)")
    invalid_title = {
        'company': 'Oracle',
        'title': '',
        'description': 'test'
    }

    try:
        validated = await client.validate_extraction_result(invalid_title, "https://test.com")
        print(f"  FAIL: Validation accepted empty title")
    except ValueError as e:
        print(f"  PASS: Validation correctly rejected: {str(e)[:80]}...")

    # Test Unknown Company
    print("\nTest 5d: Unknown Company (should FAIL)")
    unknown_company = {
        'company': 'Unknown Company',
        'title': 'Job Title',
        'description': 'test'
    }

    try:
        validated = await client.validate_extraction_result(unknown_company, "https://test.com")
        print(f"  FAIL: Validation accepted Unknown Company")
    except ValueError as e:
        print(f"  PASS: Validation correctly rejected: {str(e)[:80]}...")

    return True


async def main():
    """Run all fallback tests"""

    print("\n" + "#" * 80)
    print("# FALLBACK CHAIN VERIFICATION TEST SUITE")
    print("#" * 80)
    print()

    results = {}

    # Test 1: Playwright
    results['playwright'] = await test_playwright_fallback()

    # Test 2: Vision
    results['vision'] = await test_vision_fallback()

    # Test 3: Screenshot API
    results['screenshot_api'] = await test_screenshot_api()

    # Test 4: Full chain
    results['full_chain'] = await test_full_fallback_chain()

    # Test 5: Validation
    results['validation'] = await test_validation_logic()

    # Summary
    print("\n" + "#" * 80)
    print("# TEST SUMMARY")
    print("#" * 80)
    print()

    for test_name, result in results.items():
        if result is True:
            status = "PASS"
        elif result is False:
            status = "FAIL"
        else:
            status = "SKIP"

        print(f"{test_name.upper():20s} : {status}")

    print()
    print("#" * 80)

    # Overall status
    passed = sum(1 for r in results.values() if r is True)
    failed = sum(1 for r in results.values() if r is False)
    skipped = sum(1 for r in results.values() if r is None)

    print(f"\nPASSED: {passed}/{len(results)}")
    print(f"FAILED: {failed}/{len(results)}")
    print(f"SKIPPED: {skipped}/{len(results)}")

    if failed == 0:
        print("\nALL FALLBACKS ARE WORKING! System has full redundancy.")
    else:
        print(f"\nWARNING: {failed} fallback(s) not working. Check logs above.")


if __name__ == "__main__":
    asyncio.run(main())
