"""
GPT-4 Vision job extraction - works for ANY job site
Takes screenshot → extracts details with vision model
No browser automation needed, works in Railway without extra dependencies
"""

import base64
from io import BytesIO
from typing import Dict
import asyncio
import os


class VisionJobExtractor:
    """Extract job details using GPT-4 Vision (screenshot → extraction)"""

    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    async def extract_from_url(self, job_url: str) -> Dict[str, str]:
        """
        Extract job details from URL using screenshot + GPT-4 Vision

        Args:
            job_url: Job posting URL

        Returns:
            Dict with company, title, description, location, salary
        """
        # Step 1: Take screenshot of job page (or extract text as fallback)
        screenshot_b64, is_text = await self._capture_screenshot(job_url)

        # Step 2: Extract details using GPT-4 Vision or GPT-4 text
        extracted_data = await self._extract_with_vision(screenshot_b64, is_text=is_text)

        return extracted_data

    async def _capture_screenshot(self, url: str) -> tuple[str, bool]:
        """
        Capture screenshot using Screenshot API (works in Railway without browsers)

        Returns:
            tuple: (base64_data, is_text) where is_text=True if we extracted text instead of screenshot

        Options:
        1. ScreenshotOne API (https://screenshotone.com) - $29/mo for 10k screenshots
        2. APIFlash (https://apiflash.com) - $10/mo for 1000 screenshots
        3. ScreenshotAPI (https://screenshotapi.net) - Free tier: 100/mo
        4. FALLBACK: requests + BeautifulSoup text extraction (no screenshot)
        """
        import aiohttp

        # Try screenshot API if available
        screenshot_api_key = os.getenv('SCREENSHOT_API_KEY', '')

        if screenshot_api_key:
            # Using ScreenshotAPI.net (simple, has free tier)
            api_url = "https://shot.screenshotapi.net/screenshot"
            params = {
                'token': screenshot_api_key,
                'url': url,
                'output': 'image',
                'file_type': 'png',
                'wait_for_event': 'load',
                'delay': 2000  # Wait 2s for dynamic content
            }

            try:
                # aiohttp follows redirects by default, but let's be explicit
                async with aiohttp.ClientSession() as session:
                    async with session.get(api_url, params=params, timeout=45, allow_redirects=True) as response:
                        if response.status == 200:
                            screenshot_bytes = await response.read()
                            screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                            print(f"Screenshot captured via API ({len(screenshot_bytes)} bytes)")
                            return screenshot_b64, False  # False = it's a screenshot, not text
                        else:
                            print(f"Screenshot API error: {response.status} - {await response.text()}")
            except Exception as e:
                print(f"Screenshot API failed: {e}")

        # FALLBACK: Scrape HTML and convert to text for GPT-4 (no vision needed)
        print("No screenshot API available, using text extraction fallback...")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    html = await response.text()

                    # Extract text from HTML using BeautifulSoup
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html, 'html.parser')

                    # Remove script and style tags
                    for script in soup(["script", "style", "nav", "footer", "header"]):
                        script.decompose()

                    # Get text
                    text = soup.get_text(separator='\n', strip=True)

                    # Return as base64 with is_text=True flag
                    return base64.b64encode(text.encode('utf-8')).decode('utf-8'), True  # True = it's text, not screenshot

        except Exception as e:
            print(f"Fallback text extraction failed: {e}")
            raise Exception(f"Could not capture screenshot or extract text: {str(e)}")

    async def _extract_with_vision(self, data_b64: str, is_text: bool = False) -> Dict[str, str]:
        """
        Extract job details from screenshot using GPT-4 Vision OR from text using GPT-4

        Args:
            data_b64: Base64-encoded screenshot OR text
            is_text: If True, data_b64 is text; if False, it's a screenshot

        Returns:
            Extracted job details
        """

        if is_text:
            # Decode text from base64
            text = base64.b64decode(data_b64).decode('utf-8')
            return await self._extract_from_text(text)

        # Otherwise, use vision model for screenshot
        extraction_prompt = """Analyze this job posting screenshot and extract the following information:

1. Company name
2. Job title
3. Job description (full text - responsibilities, requirements, qualifications)
4. Location
5. Salary range (if visible)
6. Posted date (if visible)
7. Employment type (full-time, part-time, contract)
8. Experience level (entry, mid, senior, lead)
9. Required skills (as array)

Return ONLY valid JSON in this format:
{
  "company": "Company Name",
  "title": "Job Title",
  "description": "Full job description with responsibilities and requirements...",
  "location": "City, State or Remote",
  "salary": "$X - $Y" or "",
  "posted_date": "X days ago" or "",
  "employment_type": "Full-time" or "",
  "experience_level": "Senior" or "",
  "skills_required": ["Skill 1", "Skill 2"]
}

If any field is not visible in the screenshot, use empty string "" or empty array [].
Be thorough in extracting the job description - include all responsibilities and requirements visible."""

        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model="gpt-4-turbo-2024-04-09",  # GPT-4 Turbo with vision
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": extraction_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{data_b64}",
                                    "detail": "high"  # High detail for better extraction
                                },
                            },
                        ],
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=4000,
            )

            import json
            extracted = json.loads(response.choices[0].message.content)

            print(f"✓ Vision extraction succeeded: {extracted.get('company')} - {extracted.get('title')}")
            return extracted

        except Exception as e:
            print(f"Vision extraction failed: {e}")
            raise Exception(f"Failed to extract job details with vision model: {str(e)}")

    async def _extract_from_text(self, text: str) -> Dict[str, str]:
        """
        Extract job details from text using GPT-4 (no vision)

        Args:
            text: Extracted text from job page

        Returns:
            Extracted job details
        """
        extraction_prompt = f"""Analyze this job posting text and extract the following information:

Job Posting Text:
{text[:8000]}

Extract:
1. Company name
2. Job title
3. Job description (full text - responsibilities, requirements, qualifications)
4. Location
5. Salary range (if visible)
6. Posted date (if visible)
7. Employment type (full-time, part-time, contract)
8. Experience level (entry, mid, senior, lead)
9. Required skills (as array)

Return ONLY valid JSON in this format:
{{
  "company": "Company Name",
  "title": "Job Title",
  "description": "Full job description with responsibilities and requirements...",
  "location": "City, State or Remote",
  "salary": "$X - $Y" or "",
  "posted_date": "X days ago" or "",
  "employment_type": "Full-time" or "",
  "experience_level": "Senior" or "",
  "skills_required": ["Skill 1", "Skill 2"]
}}

If any field is not found in the text, use empty string "" or empty array []."""

        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model="gpt-4.1-mini",  # Use text model (cheaper than vision)
                messages=[
                    {"role": "system", "content": "You are a job posting analyzer. Extract information accurately from text."},
                    {"role": "user", "content": extraction_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=4000,
            )

            import json
            extracted = json.loads(response.choices[0].message.content)

            print(f"✓ Text extraction succeeded: {extracted.get('company')} - {extracted.get('title')}")
            return extracted

        except Exception as e:
            print(f"Text extraction failed: {e}")
            raise Exception(f"Failed to extract job details from text: {str(e)}")


# Integration function for firecrawl_client.py
async def extract_with_vision_fallback(url: str) -> Dict[str, str]:
    """
    Use GPT-4 Vision as fallback when other methods fail

    This is the most reliable method - works for ANY job site
    No browser dependencies needed in production
    """
    extractor = VisionJobExtractor()
    return await extractor.extract_from_url(url)
