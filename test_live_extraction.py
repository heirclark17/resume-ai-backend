"""
Test live production site job extraction with Oracle URL
"""

import asyncio
from playwright.async_api import async_playwright


async def test_live_extraction():
    """Test job extraction on live talorme.com site"""

    oracle_job_url = "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/jobsearch/job/318423?utm_medium=jobboard&utm_source=LinkedIn"

    print("=" * 80)
    print("TESTING LIVE PRODUCTION SITE - Job Extraction")
    print("=" * 80)
    print(f"\nTesting URL: {oracle_job_url}\n")

    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=False)  # Visible so you can see it
        page = await browser.new_page()

        try:
            # Step 1: Navigate to upload page
            print("[1/4] Navigating to https://talorme.com/upload...")
            await page.goto('https://talorme.com/upload', wait_until='networkidle')
            print("     SUCCESS: Page loaded\n")

            # Step 2: Click "Skip Upload" or navigate directly to tailor
            print("[2/4] Navigating to tailor page...")

            # Look for a way to skip upload or go directly to tailor
            # Try clicking a skip button if it exists
            skip_button = await page.query_selector('button:has-text("Skip")')
            if skip_button:
                await skip_button.click()
                await page.wait_for_timeout(1000)
            else:
                # Navigate directly to tailor page
                await page.goto('https://talorme.com/tailor', wait_until='networkidle')

            print("     SUCCESS: On tailor page\n")

            # Step 3: Paste job URL and extract
            print("[3/4] Entering job URL and clicking Extract Details...")

            # Find the job URL input field
            url_input = await page.wait_for_selector('input[placeholder*="linkedin"], input[placeholder*="job"], input[type="url"]', timeout=10000)
            await url_input.fill(oracle_job_url)
            print(f"     Entered URL: {oracle_job_url[:60]}...")

            # Click Extract Details button
            extract_button = await page.wait_for_selector('button:has-text("Extract Details"), button:has-text("Extract")', timeout=5000)
            await extract_button.click()
            print("     Clicked Extract Details button")

            # Wait for extraction to complete (look for filled company/title fields)
            print("     Waiting for extraction to complete...\n")
            await page.wait_for_timeout(5000)  # Give it time to extract

            # Step 4: Check if company and title were extracted
            print("[4/4] Checking extracted data...\n")

            # Look for company field
            company_input = await page.query_selector('input[placeholder*="company"], input[name*="company"]')
            company_value = ""
            if company_input:
                company_value = await company_input.input_value()

            # Look for job title field
            title_input = await page.query_selector('input[placeholder*="title"], input[placeholder*="position"], input[name*="title"]')
            title_value = ""
            if title_input:
                title_value = await title_input.input_value()

            # Display results
            print("=" * 80)
            print("EXTRACTION RESULTS")
            print("=" * 80)
            print(f"\nCompany:   {company_value or '[NOT EXTRACTED]'}")
            print(f"Job Title: {title_value or '[NOT EXTRACTED]'}")
            print()

            # Validation
            if company_value and title_value:
                print("=" * 80)
                print("SUCCESS: Both company and job title extracted!")
                print("=" * 80)

                # Verify Oracle job specifically
                if "oracle" in company_value.lower() and "technical program manager" in title_value.lower():
                    print("\nVERIFIED: Oracle job details match expected values")
                    print(f"  Expected Company: Oracle")
                    print(f"  Got Company:      {company_value}")
                    print(f"  Expected Title:   Senior Principal Technical Program Manager")
                    print(f"  Got Title:        {title_value}")
                else:
                    print("\nWARNING: Extracted values don't match expected Oracle job")
                    print(f"  Expected: Oracle / Senior Principal Technical Program Manager")
                    print(f"  Got:      {company_value} / {title_value}")
            else:
                print("=" * 80)
                print("FAILED: Extraction did not populate company or title fields")
                print("=" * 80)
                print("\nPossible reasons:")
                print("  - Backend extraction failed")
                print("  - Frontend not showing extracted data")
                print("  - Field selectors need updating")

            print("\n" + "=" * 80)
            print("Test complete. Browser will remain open for 10 seconds...")
            print("=" * 80)

            # Keep browser open so you can see the result
            await page.wait_for_timeout(10000)

        except Exception as e:
            print("\n" + "=" * 80)
            print("ERROR DURING TEST")
            print("=" * 80)
            print(f"\nError: {type(e).__name__}")
            print(f"Message: {str(e)}")
            import traceback
            traceback.print_exc()

        finally:
            await browser.close()


if __name__ == "__main__":
    print("\n")
    print("#" * 80)
    print("# LIVE PRODUCTION SITE TEST")
    print("#" * 80)
    print()

    asyncio.run(test_live_extraction())

    print()
    print("#" * 80)
    print("# TEST COMPLETE")
    print("#" * 80)
    print()
