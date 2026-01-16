"""
Test Vision/text extraction to debug why title is not being captured
"""

import asyncio
import aiohttp
import base64
from bs4 import BeautifulSoup


async def test_text_extraction():
    """Test what the Vision extractor is actually seeing"""

    oracle_url = "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/jobsearch/job/318423?utm_medium=jobboard&utm_source=LinkedIn"

    print("=" * 80)
    print("TESTING TEXT EXTRACTION (simulating Vision fallback)")
    print("=" * 80)
    print(f"\nURL: {oracle_url}\n")

    try:
        # Step 1: Extract HTML (same as vision_extractor.py lines 85-101)
        print("[1/3] Fetching HTML...")
        async with aiohttp.ClientSession() as session:
            async with session.get(oracle_url, timeout=30) as response:
                html = await response.text()
                print(f"     HTML fetched: {len(html)} characters\n")

        # Step 2: Parse with BeautifulSoup (same as vision_extractor.py)
        print("[2/3] Extracting text with BeautifulSoup...")
        soup = BeautifulSoup(html, 'html.parser')

        # Remove script and style tags
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.decompose()

        # Get text
        text = soup.get_text(separator='\n', strip=True)
        print(f"     Extracted text: {len(text)} characters\n")

        # Step 3: Show what GPT-4.1-mini sees (first 8000 chars)
        print("[3/3] Analyzing extracted text...\n")
        print("=" * 80)
        print("FIRST 8000 CHARACTERS (what GPT-4.1-mini sees):")
        print("=" * 80)
        print(text[:8000])
        print("\n" + "=" * 80)

        # Step 4: Search for job title keywords
        print("\nSEARCHING FOR JOB TITLE KEYWORDS:")
        print("=" * 80)

        keywords = [
            "Senior Principal Technical Program Manager",
            "Technical Program Manager",
            "Program Manager",
            "Job Title",
            "Position",
            "title"
        ]

        for keyword in keywords:
            if keyword.lower() in text.lower():
                # Find position of keyword
                pos = text.lower().find(keyword.lower())
                # Show context around keyword
                start = max(0, pos - 100)
                end = min(len(text), pos + 200)
                context = text[start:end]
                print(f"\nFound '{keyword}' at position {pos}:")
                print(f"Context: ...{context}...")

                if pos >= 8000:
                    print(f"  WARNING: This is AFTER the 8000 char limit!")
                else:
                    print(f"  OK: Within first 8000 characters")

        # Step 5: Save full text for analysis
        print("\n" + "=" * 80)
        print("SAVING FULL TEXT TO FILE")
        print("=" * 80)

        with open("oracle_extracted_text.txt", "w", encoding="utf-8") as f:
            f.write(text)

        print(f"\nFull extracted text saved to: oracle_extracted_text.txt")
        print(f"Total length: {len(text)} characters")
        print(f"GPT-4.1-mini only sees first 8000 characters ({(8000/len(text)*100):.1f}% of page)")

    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_text_extraction())
