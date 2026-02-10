"""STAR Story to Interview Question Matching Service"""

import os
import json
from openai import AsyncOpenAI
from typing import List


async def match_stories_to_questions(
    stories: List[dict],
    questions: List[str],
) -> List[dict]:
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    stories_text = "\n".join(
        f"Story {i+1} (ID: {s['id']}): {s.get('title', 'Untitled')} - "
        f"Situation: {s.get('situation', '')[:100]}... "
        f"Result: {s.get('result', '')[:100]}..."
        for i, s in enumerate(stories)
    )

    questions_text = "\n".join(
        f"Question {i+1}: {q}" for i, q in enumerate(questions)
    )

    prompt = f"""Match the following STAR stories to the interview questions based on relevance.

STAR STORIES:
{stories_text}

INTERVIEW QUESTIONS:
{questions_text}

For each question, return the top 2-3 most relevant STAR stories with a relevance score (0-100).

Return a JSON object:
{{
  "matches": [
    {{
      "question": "The interview question text",
      "question_index": 0,
      "recommended_stories": [
        {{
          "story_id": 1,
          "story_title": "Story title",
          "relevance_score": 85,
          "reasoning": "Brief explanation of why this story fits"
        }}
      ]
    }}
  ]
}}"""

    response = await client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "You are an expert interview coach matching STAR stories to interview questions."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=3000,
    )

    result = json.loads(response.choices[0].message.content)
    return result.get("matches", [])
