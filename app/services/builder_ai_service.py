"""Builder AI Service - OpenAI calls for resume builder features"""

import os
import json
from openai import AsyncOpenAI
from typing import Optional


class BuilderAIService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4.1-mini"

    async def generate_summaries(
        self,
        job_title: str,
        years_experience: str = "",
        highlights: list[str] | None = None,
        existing_skills: list[str] | None = None,
        tone: str = "professional",
    ) -> list[str]:
        """Generate 3 professional summary variants."""
        highlights_str = "\n".join(f"- {h}" for h in (highlights or []))
        skills_str = ", ".join(existing_skills or [])

        prompt = f"""Generate 3 different professional summary variants for a resume.

Job Title / Most Recent Role: {job_title}
{f"Years of Experience: {years_experience}" if years_experience else ""}
{f"Career Highlights:\n{highlights_str}" if highlights_str else ""}
{f"Skills: {skills_str}" if skills_str else ""}
Tone: {tone}

Requirements:
- Each variant should be 3-5 sentences
- Use strong action language and quantifiable achievements
- First variant: results-focused, emphasizing measurable impact
- Second variant: skills-focused, highlighting technical expertise
- Third variant: leadership-focused, emphasizing team and project management
- Do NOT use placeholder brackets or generic filler
- Be specific and compelling

Return ONLY a JSON array of 3 strings. No other text."""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert resume writer. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.8,
            max_tokens=1200,
        )

        text = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        return json.loads(text)

    async def enhance_bullets(
        self,
        job_title: str,
        company: str,
        bullets: list[str],
        mode: str = "enhance",
    ) -> list[str]:
        """Enhance experience bullet points with stronger action verbs and metrics."""
        bullets_str = "\n".join(f"- {b}" for b in bullets)

        prompt = f"""Enhance these resume bullet points for a {job_title} role at {company}.

Current bullets:
{bullets_str}

Requirements:
- Start each bullet with a strong action verb (Led, Built, Delivered, Optimized, etc.)
- Add quantifiable metrics where possible (%, $, team size, timeframes)
- Keep each bullet to 1-2 lines
- Make achievements specific and impactful
- Maintain truthfulness — enhance framing, don't fabricate
- Return the same number of bullets as provided

Return ONLY a JSON array of strings. No other text."""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert resume writer. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=800,
        )

        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        return json.loads(text)

    async def suggest_skills(
        self,
        job_title: str,
        existing_skills: list[str] | None = None,
        experience_titles: list[str] | None = None,
    ) -> dict:
        """Suggest categorized skills based on role and experience."""
        existing_str = ", ".join(existing_skills or [])
        titles_str = ", ".join(experience_titles or [])

        prompt = f"""Suggest relevant skills for someone with this background:

Target/Recent Role: {job_title}
{f"Experience in: {titles_str}" if titles_str else ""}
{f"Already listed: {existing_str}" if existing_str else ""}

Requirements:
- Suggest skills NOT already in their list
- Organize into 3-4 categories (e.g., "Technical Skills", "Soft Skills", "Tools & Platforms", "Frameworks")
- 4-6 skills per category
- Focus on in-demand, ATS-friendly skills
- Be specific (e.g., "React.js" not just "JavaScript frameworks")

Return ONLY a JSON object with this structure:
{{"categories": {{"Category Name": ["skill1", "skill2", ...]}}, "suggested_skills": ["all", "skills", "flat"]}}
No other text."""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a career coach and ATS optimization expert. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
            max_tokens=600,
        )

        text = response.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        return json.loads(text)


# Singleton
builder_ai_service = BuilderAIService()
