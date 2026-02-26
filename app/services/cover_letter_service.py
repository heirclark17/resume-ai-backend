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
    length: str = "standard",
    focus: str = "program_management",
    resume_context: Optional[dict] = None,
    company_research: Optional[dict] = None,
) -> str:
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    tone_instructions = {
        "professional": "Use a formal, polished tone. Be direct and confident.",
        "enthusiastic": "Use an energetic, passionate tone. Show excitement for the role.",
        "conversational": "Use a friendly, approachable tone. Be personable and warm.",
        "strategic": "Use a strategic, results-oriented tone. Emphasize vision and impact.",
        "technical": "Use a technically precise tone. Highlight technical depth and expertise.",
    }

    length_instructions = {
        "concise": "Write 3 paragraphs (250-300 words).",
        "standard": "Write 4 paragraphs (300-400 words).",
        "detailed": "Write 5 paragraphs (400-500 words).",
    }

    focus_instructions = {
        "leadership": "Emphasize leadership experience, team management, and strategic decision-making.",
        "technical": "Emphasize technical expertise, tools, frameworks, and hands-on experience.",
        "program_management": "Emphasize program/project management, delivery, and cross-team coordination.",
        "cross_functional": "Emphasize cross-functional collaboration, stakeholder management, and communication.",
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

    research_section = ""
    if company_research and company_research.get("research"):
        research_section = f"""
COMPANY RESEARCH (use this to personalize the letter):
{company_research['research']}
"""

    prompt = f"""Generate a compelling cover letter for the following position.

JOB DETAILS:
- Title: {job_title}
- Company: {company_name}
- Description: {job_description}
{resume_section}{research_section}
TONE: {tone_instructions.get(tone, tone_instructions['professional'])}
LENGTH: {length_instructions.get(length, length_instructions['standard'])}
FOCUS: {focus_instructions.get(focus, focus_instructions['program_management'])}

REQUIREMENTS:
- Write a complete cover letter with greeting, body paragraphs, and professional closing
- Reference specific job requirements from the description
- If resume context is provided, connect the candidate's experience to the role
- If company research is provided, reference the company's mission, values, or recent initiatives to demonstrate cultural fit and genuine interest
- Include measurable achievements where possible
- Keep it to one page (300-400 words)
- Do NOT include placeholder brackets like [Your Name] — write it as a complete letter
- Address it to the hiring manager at {company_name}
- Sign off with the candidate's name if available

Return ONLY the cover letter text, no JSON or markdown formatting."""

    response = await client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "You are an expert career coach who writes compelling, deeply tailored cover letters. When company research is provided, weave in references to the company's mission, values, recent initiatives, and culture to show genuine knowledge and alignment. When resume context is provided, connect the candidate's specific experience and achievements to the job requirements."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=2500,
    )

    return response.choices[0].message.content.strip()
