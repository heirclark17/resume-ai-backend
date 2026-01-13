"""
Playwright-based job extraction for sites that block Firecrawl
Handles JavaScript-heavy sites and anti-bot protection
"""

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout, Error as PlaywrightError
from typing import Dict, Optional
import asyncio
import re
import os


class PlaywrightJobExtractor:
    """Extract job details using Playwright browser automation"""

    async def extract_job_details(self, url: str) -> Dict[str, str]:
        """
        Extract job details from URL using Playwright

        Args:
            url: Job posting URL

        Returns:
            Dict with company, title, description, location, salary
        """

        try:
            async with async_playwright() as p:
                # Launch browser (headless for production)
                # Add extra arguments for Railway/containerized environments
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-accelerated-2d-canvas',
                        '--disable-gpu'
                    ]
                )
                page = await browser.new_page()

                try:
                    print(f"[Playwright] Navigating to: {url}")

                    # Navigate with generous timeout for slow sites
                    await page.goto(url, wait_until="networkidle", timeout=30000)

                    # Wait for content to load
                    await page.wait_for_timeout(2000)

                    # Get page title for fallback
                    page_title = await page.title()

                    # Extract job details using multiple strategies
                    job_data = {
                        "company": await self._extract_company(page, url),
                        "title": await self._extract_title(page, page_title),
                        "description": await self._extract_description(page),
                        "location": await self._extract_location(page),
                        "salary": await self._extract_salary(page),
                    }

                    print(f"[Playwright] Extracted: {job_data['company']} - {job_data['title']}")

                    await browser.close()
                    return job_data

                except PlaywrightTimeout as e:
                    print(f"[Playwright] Timeout error: {e}")
                    await browser.close()
                    raise Exception(f"Page load timeout: {url}")
                except Exception as e:
                    print(f"[Playwright] Extraction error: {e}")
                    await browser.close()
                    raise Exception(f"Failed to extract job details: {str(e)}")

    async def _extract_company(self, page, url: str) -> str:
        """Extract company name from page"""

        # Strategy 1: Common selectors for company name
        selectors = [
            '[data-automation-id="company"]',
            '[class*="company"]',
            '[class*="employer"]',
            'meta[property="og:site_name"]',
            'a[href*="/company/"]',
            '.company-name',
            '#company-name',
        ]

        for selector in selectors:
            try:
                elem = await page.query_selector(selector)
                if elem:
                    # Check if it's a meta tag
                    if selector.startswith('meta'):
                        company = await elem.get_attribute('content')
                    else:
                        company = await elem.inner_text()

                    if company and len(company) > 2:
                        return company.strip()
            except:
                continue

        # Strategy 2: Extract from URL
        domain_map = {
            'microsoft.com': 'Microsoft',
            'oracle.com': 'Oracle',
            'amazon.jobs': 'Amazon',
            'google.com': 'Google',
            'apple.com': 'Apple',
            'greenhouse.io': self._extract_from_greenhouse_url(url),
        }

        for domain, company in domain_map.items():
            if domain in url:
                return company

        # Strategy 3: Look for company name in page text
        body_text = await page.inner_text('body')

        # Common patterns: "at Company" or "Company is hiring"
        patterns = [
            r'(?:at|@)\s+([A-Z][a-zA-Z\s&]+?)(?:\s+is|\s+\||$)',
            r'([A-Z][a-zA-Z\s&]+?)\s+is\s+(?:hiring|recruiting|looking)',
        ]

        for pattern in patterns:
            match = re.search(pattern, body_text)
            if match:
                return match.group(1).strip()

        return "Unknown Company"

    async def _extract_title(self, page, page_title: str) -> str:
        """Extract job title from page"""

        # Strategy 1: Common selectors for job title
        selectors = [
            'h1',
            '[data-automation-id="jobTitle"]',
            '[class*="job-title"]',
            '[class*="jobTitle"]',
            'meta[property="og:title"]',
            '.job-title',
            '#job-title',
        ]

        for selector in selectors:
            try:
                elem = await page.query_selector(selector)
                if elem:
                    # Check if it's a meta tag
                    if selector.startswith('meta'):
                        title = await elem.get_attribute('content')
                    else:
                        title = await elem.inner_text()

                    if title and len(title) > 5 and len(title) < 200:
                        # Clean up title
                        title = title.strip()
                        # Remove common suffixes
                        title = re.sub(r'\s*\|\s*.*$', '', title)  # Remove "| Company"
                        title = re.sub(r'\s*-\s*.*$', '', title)   # Remove "- Company"
                        return title
            except:
                continue

        # Strategy 2: Use page title
        if page_title:
            # Remove common suffixes from page title
            title = re.sub(r'\s*\|\s*.*$', '', page_title)
            title = re.sub(r'\s*-\s*.*$', '', title)
            if len(title) > 5:
                return title.strip()

        return "Unknown Position"

    async def _extract_description(self, page) -> str:
        """Extract job description from page"""

        # Strategy 1: Common selectors for job description
        selectors = [
            '[class*="job-description"]',
            '[class*="description"]',
            '[id*="job-description"]',
            '[data-automation-id="jobDescription"]',
            'article',
            '.description',
            '#description',
        ]

        for selector in selectors:
            try:
                elem = await page.query_selector(selector)
                if elem:
                    description = await elem.inner_text()
                    if description and len(description) > 100:
                        return description.strip()
            except:
                continue

        # Strategy 2: Get all text from main content
        try:
            main_selectors = ['main', '[role="main"]', '#main-content', '.main-content']
            for selector in main_selectors:
                elem = await page.query_selector(selector)
                if elem:
                    text = await elem.inner_text()
                    if len(text) > 100:
                        return text.strip()
        except:
            pass

        # Strategy 3: Get all body text (less ideal)
        body_text = await page.inner_text('body')

        # Try to extract just the description part (after job title, before footer)
        lines = body_text.split('\n')
        relevant_lines = []
        in_description = False

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Start capturing after common headers
            if any(keyword in line.lower() for keyword in ['description', 'responsibilities', 'qualifications', 'requirements']):
                in_description = True

            # Stop at footer indicators
            if any(keyword in line.lower() for keyword in ['privacy policy', 'cookie policy', 'terms of service', 'copyright']):
                break

            if in_description:
                relevant_lines.append(line)

        if relevant_lines:
            return '\n'.join(relevant_lines[:100])  # Limit to 100 lines

        # Fallback: return first 3000 characters of body
        return body_text[:3000]

    async def _extract_location(self, page) -> str:
        """Extract job location from page"""

        selectors = [
            '[data-automation-id="location"]',
            '[class*="location"]',
            '[class*="job-location"]',
            'meta[property="og:locality"]',
            '.location',
            '#location',
        ]

        for selector in selectors:
            try:
                elem = await page.query_selector(selector)
                if elem:
                    if selector.startswith('meta'):
                        location = await elem.get_attribute('content')
                    else:
                        location = await elem.inner_text()

                    if location and len(location) > 2:
                        return location.strip()
            except:
                continue

        return ""

    async def _extract_salary(self, page) -> str:
        """Extract salary information from page"""

        selectors = [
            '[data-automation-id="salary"]',
            '[class*="salary"]',
            '[class*="compensation"]',
            '.salary',
            '#salary',
        ]

        for selector in selectors:
            try:
                elem = await page.query_selector(selector)
                if elem:
                    salary = await elem.inner_text()
                    if salary and ('$' in salary or 'k' in salary.lower()):
                        return salary.strip()
            except:
                continue

        # Look for salary in body text
        body_text = await page.inner_text('body')

        # Pattern: $100,000 - $150,000 or $100k - $150k
        salary_patterns = [
            r'\$[\d,]+(?:k|K)?\s*-\s*\$[\d,]+(?:k|K)?',
            r'\$[\d,]+(?:\.\d+)?[kK]?(?:\s*-\s*\$[\d,]+(?:\.\d+)?[kK]?)?',
        ]

        for pattern in salary_patterns:
            match = re.search(pattern, body_text)
            if match:
                return match.group(0)

        return ""

    def _extract_from_greenhouse_url(self, url: str) -> str:
        """Extract company name from Greenhouse URL"""
        # Greenhouse URLs: https://boards.greenhouse.io/companyname/jobs/...
        match = re.search(r'greenhouse\.io/([^/]+)', url)
        if match:
            company = match.group(1).replace('-', ' ').title()
            return company
        return "Unknown Company"


# Integration with existing firecrawl_client.py
async def extract_with_playwright_fallback(url: str) -> Dict[str, str]:
    """
    Use Playwright as fallback when Firecrawl fails

    Usage in firecrawl_client.py:

    try:
        # Try Firecrawl first
        result = await firecrawl.scrape(url)
        ...
    except Exception as e:
        # Fallback to Playwright
        from app.services.playwright_extractor import extract_with_playwright_fallback
        result = await extract_with_playwright_fallback(url)
    """

    extractor = PlaywrightJobExtractor()
    return await extractor.extract_job_details(url)
