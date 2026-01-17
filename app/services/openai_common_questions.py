"""
OpenAI service for generating tailored common interview questions

Sources consulted for best practices:
- Indeed: Tell me about yourself (Present/Past/Future framework, 2min max, focus on relevant experience)
- HBR: Why should we hire you (Focus on match, emphasize uniqueness, make vision statements)
- The Muse: Weaknesses (Turn into growth story, show self-awareness)
- Big Interview: STAR method (Situation 15%, Task 10%, Action 60%, Result 15% with metrics)
"""

import os
from openai import AsyncOpenAI
import json
from typing import Dict, Any

class OpenAICommonQuestions:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4.1-mini"

    async def generate_common_questions(
        self,
        resume_text: str,
        job_description: str,
        company_name: str,
        job_title: str,
        prep_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate tailored responses for 10 common interview questions

        Args:
            resume_text: Structured resume text with experience, skills, etc.
            job_description: Full job description text
            company_name: Name of company
            job_title: Position title
            prep_data: Interview prep data with company research, role analysis, etc.

        Returns:
            Dictionary with 10 tailored interview question responses
        """

        system_prompt = """You are an expert interview coach with deep knowledge of behavioral interviewing,
STAR method, and proven frameworks for answering common interview questions. Your expertise comes from:

- Indeed's Present/Past/Future framework for "Tell me about yourself"
- HBR's approach for "Why should we hire you" (focus on match, uniqueness, vision)
- STAR method structure: Situation (15%), Task (10%), Action (60%), Result (15%)
- Using measurable outcomes (%, $, scale, time saved) whenever possible
- Connecting candidate experience directly to job requirements

You generate EXCEPTIONAL, TAILORED interview answers that:
1. Use specific details from the candidate's resume
2. Connect directly to the job description requirements
3. Include quantifiable metrics when available
4. Sound natural and speakable, not scripted
5. Demonstrate self-awareness and growth mindset
6. Follow proven frameworks (STAR for behavioral, Present/Past/Future for "tell me about yourself")

CRITICAL: Your answers must NOT be generic. Every answer must reference:
- Specific achievements from the candidate's resume
- Specific requirements from the job description
- The company's mission, values, or recent initiatives when relevant

If specific metrics aren't available, create credible placeholder formats like "[X%] reduction"
that the candidate can customize with their actual numbers."""

        user_prompt = f"""Generate tailored responses for these 10 common interview questions.

CANDIDATE RESUME:
{resume_text}

JOB INFORMATION:
Company: {company_name}
Role: {job_title}
Description:
{job_description}

COMPANY RESEARCH & ROLE ANALYSIS:
{json.dumps(prep_data, indent=2)}

For EACH of the 10 questions below, provide:

1. question: The exact question text
2. why_hard: 2-4 sentences explaining why this question is challenging (plain English, not generic)
3. common_mistakes: 4-8 specific mistakes candidates make (bullet points)
4. exceptional_answer_builder: Detailed, tailored guidance including:
   - structure: Step-by-step approach (array of strings)
   - customization_checklist: What to pull from resume + JD (array of strings)
   - strong_phrases: Powerful phrases to use (array of strings)
5. what_to_say: Two versions of the answer:
   - short: 60-120 words (elevator pitch version)
   - long: 150-250 words (full detailed version)
   - placeholders_used: Which resume/JD facts were inserted (array)

THE 10 QUESTIONS (use exactly these):

1. "Tell me about yourself."
   - Framework: Present/Past/Future
   - Must connect current role → past experience → future goals with THIS job
   - Keep to ~2 minutes (150-200 words for long version)
   - Focus on professional journey, not personal life

2. "What are your weaknesses?"
   - Must be a REAL weakness (not "I work too hard")
   - Show self-awareness and growth
   - Include what you're doing to improve
   - Connect to role requirements (show it won't impact job performance)

3. "Why do you want to work here?"
   - Reference specific company initiatives from the research
   - Connect to candidate's values and career goals
   - Show you've done your homework
   - Make it about their mission, not just "it's a good opportunity"

4. "Tell me about a time you failed."
   - STAR method (focus 60% on Action, 15% on Result with lesson learned)
   - Choose relevant failure (related to this job's competencies)
   - Show vulnerability but also growth
   - Quantify the impact if possible

5. "What's your biggest achievement?"
   - STAR method with heavy emphasis on measurable Result
   - Choose achievement relevant to this role
   - Include specific metrics (%, $, scale)
   - Show how you can replicate success here

6. "Why should we hire you?"
   - Focus on the MATCH (their needs + your skills)
   - Reference specific JD requirements
   - Make "vision statements" (paint picture of you succeeding)
   - 3-4 unique selling points with evidence

7. "Where do you see yourself in 5 years?"
   - Connect to company's growth trajectory
   - Show ambition but realism
   - Align with career paths available at this company
   - Demonstrate commitment (not "I want your boss's job")

8. "Tell me about a conflict at work."
   - STAR method with focus on resolution approach
   - Show emotional intelligence and communication skills
   - Emphasize positive outcome
   - Demonstrate maturity and professionalism

9. "Describe a time you led something."
   - STAR method emphasizing leadership style
   - Quantify team size, scope, impact
   - Show ability to inspire and delegate
   - Connect to leadership expectations of THIS role

10. "Do you have any questions for us?"
    - Provide 6-10 HIGH-QUALITY questions the candidate can ask
    - Include at least 2 technical/role-specific questions
    - Include at least 2 culture/process questions
    - Prioritize by relevance to company and role
    - Show you've researched the company

RESPONSE FORMAT:
Return a JSON object with this exact structure:

{{
  "questions": [
    {{
      "id": "q1",
      "question": "Tell me about yourself.",
      "why_hard": "2-4 sentences explaining the challenge",
      "common_mistakes": [
        "Being too generic or talking only about personal life",
        "Rambling without structure or focus",
        "Not connecting experience to this specific role",
        "Going over 2 minutes or being too brief"
      ],
      "exceptional_answer_builder": {{
        "structure": [
          "Start with your current role and key achievement",
          "Work backward through 2-3 relevant past experiences",
          "Connect to why you're excited about THIS opportunity"
        ],
        "customization_checklist": [
          "Pull top 3-4 achievements from resume that match JD",
          "Reference specific company initiatives or values",
          "Use metrics where possible (%, $, scale)"
        ],
        "strong_phrases": [
          "In my current role as [X], I've successfully...",
          "My background in [Y] has prepared me to...",
          "I'm particularly drawn to your company because..."
        ]
      }},
      "what_to_say": {{
        "short": "60-120 word version using candidate's actual experience",
        "long": "150-250 word version with more detail and metrics",
        "placeholders_used": [
          "[Specific achievement from resume]",
          "[Company initiative mentioned]",
          "[Quantifiable result like 23% increase]"
        ]
      }}
    }},
    ... 9 more questions
  ]
}}

CRITICAL REQUIREMENTS:
- Use ONLY information from the candidate's resume and JD provided
- Include specific metrics from their experience (or placeholder formats)
- Reference company research data when relevant
- Make "what_to_say" sound NATURAL and SPEAKABLE, not robotic
- Ensure every answer is TAILORED, not generic advice
- For question 10, list actual questions (not meta-advice)

Generate all 10 now. Return valid JSON only."""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content)
            return result

        except Exception as e:
            print(f"Error generating common questions: {e}")
            raise Exception(f"Failed to generate common questions: {str(e)}")
