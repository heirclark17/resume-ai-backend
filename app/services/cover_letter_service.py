"""Cover Letter Generation Service"""

import os
import json
from openai import AsyncOpenAI
from typing import Optional


async def generate_cover_letter_content(
    job_title: str,
    company_name: str,
    job_description: str,
    tone: str = "professional",
    resume_context: Optional[dict] = None,
) -> str:
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    tone_instructions = {
        "professional": "Use a formal, polished tone. Be direct and confident.",
        "enthusiastic": "Use an energetic, passionate tone. Show excitement for the role.",
        "conversational": "Use a friendly, approachable tone. Be personable and warm.",
    }

    resume_section = ""
    if resume_context:
        resume_section = f"""
CANDIDATE RESUME CONTEXT:
Name: {resume_context.get('name', 'Candidate')}
Summary: {resume_context.get('summary', '')}
Skills: {resume_context.get('skills', '')}
Experience: {resume_context.get('experience', '')}
"""

    prompt = f"""Generate a compelling cover letter for the following position.

JOB DETAILS:
- Title: {job_title}
- Company: {company_name}
- Description: {job_description}
{resume_section}
TONE: {tone_instructions.get(tone, tone_instructions['professional'])}

REQUIREMENTS:
- Write a complete cover letter with greeting, 3-4 body paragraphs, and professional closing
- Reference specific job requirements from the description
- If resume context is provided, connect the candidate's experience to the role
- Include measurable achievements where possible
- Keep it to one page (300-400 words)
- Do NOT include placeholder brackets like [Your Name] — write it as a complete letter
- Address it to the hiring manager at {company_name}
- Sign off with the candidate's name if available

Return ONLY the cover letter text, no JSON or markdown formatting."""

    response = await client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "You are an expert career coach who writes compelling, tailored cover letters."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=2000,
    )

    return response.choices[0].message.content.strip()
