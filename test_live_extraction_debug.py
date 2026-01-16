"""
Debug test for live production site job extraction
Captures network requests and console logs
"""

import asyncio
from playwright.async_api import async_playwright
import json


async def test_live_extraction_debug():
    """Test job extraction with full debugging"""

    oracle_job_url = "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/jobsearch/job/318423?utm_medium=jobboard&utm_source=LinkedIn"

    print("=" * 80)
    print("DEBUGGING LIVE JOB EXTRACTION")
    print("=" * 80)
    print(f"\nJob URL: {oracle_job_url}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # Capture console logs
        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))

        # Capture network requests
        api_responses = []

        async def handle_response(response):
            """Capture API responses"""
            if '/api/jobs/extract' in response.url or '/extract' in response.url:
                try:
                    body = await response.json()
                    api_responses.append({
                        'url': response.url,
                        'status': response.status,
                        'body': body
                    })
                    print(f"\n[API RESPONSE] {response.url}")
                    print(f"Status: {response.status}")
                    print(f"Body: {json.dumps(body, indent=2)}\n")
                except:
                    text = await response.text()
                    api_responses.append({
                        'url': response.url,
                        'status': response.status,
                        'body': text[:500]
                    })
                    print(f"\n[API RESPONSE] {response.url}")
                    print(f"Status: {response.status}")
                    print(f"Body (text): {text[:200]}...\n")

        page.on("response", handle_response)

        try:
            # Navigate to tailor page directly
            print("[1/3] Navigating to tailor page...")
            await page.goto('https://talorme.com/tailor', wait_until='networkidle')
            print("     Page loaded\n")

            # Wait a bit for any initial loading
            await page.wait_for_timeout(2000)

            # Find and fill the job URL input
            print("[2/3] Looking for job URL input field...")

            # Try multiple selectors
            url_input = None
            selectors_to_try = [
                'input[placeholder*="LinkedIn"]',
                'input[placeholder*="linkedin"]',
                'input[placeholder*="job URL"]',
                'input[placeholder*="Job URL"]',
                'input[type="url"]',
                'input[name*="url"]',
                'input[id*="url"]'
            ]

            for selector in selectors_to_try:
                try:
                    url_input = await page.query_selector(selector)
                    if url_input:
                        print(f"     Found input with selector: {selector}")
                        break
                except:
                    continue

            if not url_input:
                print("     ERROR: Could not find job URL input field!")
                print("     Checking all input fields on page...")

                inputs = await page.query_selector_all('input')
                for i, inp in enumerate(inputs):
                    placeholder = await inp.get_attribute('placeholder')
                    name = await inp.get_attribute('name')
                    input_type = await inp.get_attribute('type')
                    print(f"       Input {i}: type={input_type}, name={name}, placeholder={placeholder}")

                return

            # Fill the URL
            await url_input.fill(oracle_job_url)
            print(f"     Entered URL\n")

            # Find and click Extract button
            print("[3/3] Looking for Extract Details button...")

            extract_button = None
            button_selectors = [
                'button:has-text("Extract Details")',
                'button:has-text("Extract")',
                'button:has-text("extract")',
                'button[type="button"]'
            ]

            for selector in button_selectors:
                try:
                    extract_button = await page.query_selector(selector)
                    if extract_button:
                        text = await extract_button.inner_text()
                        if 'extract' in text.lower():
                            print(f"     Found button: {text}")
                            break
                except:
                    continue

            if not extract_button:
                print("     ERROR: Could not find Extract button!")
                print("     Checking all buttons on page...")

                buttons = await page.query_selector_all('button')
                for i, btn in enumerate(buttons):
                    text = await btn.inner_text()
                    print(f"       Button {i}: {text}")
                return

            # Click extract
            print("     Clicking Extract Details...")
            await extract_button.click()

            # Wait for API call to complete
            print("     Waiting for API response...\n")
            await page.wait_for_timeout(8000)

            # Check if company/title fields got populated
            print("\n" + "=" * 80)
            print("CHECKING FORM FIELDS")
            print("=" * 80)

            # Try to find company and title fields
            all_inputs = await page.query_selector_all('input')
            print(f"\nFound {len(all_inputs)} input fields on page:")

            for i, inp in enumerate(all_inputs):
                try:
                    placeholder = await inp.get_attribute('placeholder') or ''
                    name = await inp.get_attribute('name') or ''
                    value = await inp.input_value() or ''

                    if value or 'company' in placeholder.lower() or 'title' in placeholder.lower():
                        print(f"  [{i}] placeholder='{placeholder}', name='{name}', value='{value}'")
                except:
                    pass

            # Display API responses
            print("\n" + "=" * 80)
            print("API RESPONSES CAPTURED")
            print("=" * 80)

            if api_responses:
                for resp in api_responses:
                    print(f"\nURL: {resp['url']}")
                    print(f"Status: {resp['status']}")
                    print(f"Response: {json.dumps(resp['body'], indent=2)[:500]}...")
            else:
                print("\nNO API RESPONSES CAPTURED!")
                print("The Extract Details button may not have triggered an API call.")

            # Display console logs
            print("\n" + "=" * 80)
            print("CONSOLE LOGS")
            print("=" * 80)

            if console_logs:
                for log in console_logs[-20:]:  # Last 20 logs
                    print(log)
            else:
                print("\nNo console logs captured")

            print("\n" + "=" * 80)
            print("Browser will remain open for 15 seconds for inspection...")
            print("=" * 80)

            await page.wait_for_timeout(15000)

        except Exception as e:
            print("\n" + "=" * 80)
            print("ERROR")
            print("=" * 80)
            print(f"\n{type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(test_live_extraction_debug())
