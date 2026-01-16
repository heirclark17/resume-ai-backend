"""
Test job extraction with Oracle job URL
Tests the enhanced Playwright extractor with structured data extraction
"""

import asyncio
import sys
import os

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.playwright_extractor import PlaywrightJobExtractor


async def test_oracle_job_extraction():
    """Test extraction from Oracle job posting"""

    job_url = "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/jobsearch/job/318423?utm_medium=jobboard&utm_source=LinkedIn"

    print("=" * 80)
    print("TESTING JOB EXTRACTION - Oracle HCM Job Posting")
    print("=" * 80)
    print(f"\nURL: {job_url}\n")

    try:
        # Initialize Playwright extractor
        extractor = PlaywrightJobExtractor()

        print("Starting Playwright extraction...\n")

        # Extract job details
        result = await extractor.extract_job_details(job_url)

        print("\n" + "=" * 80)
        print(" EXTRACTION SUCCESSFUL")
        print("=" * 80)

        # Display results
        print(f"\n EXTRACTED DATA:\n")
        print(f"  Company:     {result.get('company', 'N/A')}")
        print(f"  Title:       {result.get('title', 'N/A')}")
        print(f"  Location:    {result.get('location', 'N/A')}")
        print(f"  Salary:      {result.get('salary', 'N/A')}")
        print(f"\n  Description: {result.get('description', 'N/A')[:200]}...")

        print("\n" + "=" * 80)

        # Validate results
        if result.get('company') and result.get('title'):
            print(" VALIDATION PASSED - Company and Title extracted successfully")
        else:
            print("  VALIDATION WARNING - Missing company or title")

        return result

    except Exception as e:
        print("\n" + "=" * 80)
        print(" EXTRACTION FAILED")
        print("=" * 80)
        print(f"\nError: {type(e).__name__}")
        print(f"Message: {str(e)}")
        import traceback
        print("\nFull traceback:")
        traceback.print_exc()
        return None


async def test_with_firecrawl_fallback():
    """Test full extraction chain (Firecrawl → OpenAI → Playwright → Vision)"""

    job_url = "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/jobsearch/job/318423?utm_medium=jobboard&utm_source=LinkedIn"

    print("\n" + "=" * 80)
    print("TESTING FULL EXTRACTION CHAIN")
    print("=" * 80)
    print(f"\nURL: {job_url}\n")

    try:
        from app.services.firecrawl_client import FirecrawlClient

        firecrawl = FirecrawlClient()

        print(" Starting full extraction chain (Firecrawl → OpenAI → Playwright → Vision)...\n")

        result = await firecrawl.extract_job_details(job_url)

        print("\n" + "=" * 80)
        print(" FULL CHAIN EXTRACTION SUCCESSFUL")
        print("=" * 80)

        print(f"\n FINAL EXTRACTED DATA:\n")
        print(f"  Company:     {result.get('company', 'N/A')}")
        print(f"  Title:       {result.get('title', 'N/A')}")
        print(f"  Location:    {result.get('location', 'N/A')}")
        print(f"  Salary:      {result.get('salary', 'N/A')}")
        print(f"\n  Description: {result.get('description', 'N/A')[:300]}...")

        print("\n" + "=" * 80)

        return result

    except Exception as e:
        print("\n" + "=" * 80)
        print(" FULL CHAIN EXTRACTION FAILED")
        print("=" * 80)
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """Run both tests"""

    print("\n" + "#" * 80)
    print("# JOB EXTRACTION TEST SUITE")
    print("#" * 80)

    # Test 1: Playwright only (shows if structured data works)
    playwright_result = await test_oracle_job_extraction()

    # Test 2: Full chain (shows complete fallback behavior)
    await test_with_firecrawl_fallback()

    print("\n" + "#" * 80)
    print("# TEST SUITE COMPLETE")
    print("#" * 80)
    print()


if __name__ == "__main__":
    # Run async main
    asyncio.run(main())
