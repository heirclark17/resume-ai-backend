from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel
from typing import List, Optional, Dict
from app.database import get_db
from app.models.star_story import StarStory
from datetime import datetime
from openai import AsyncOpenAI
from app.config import get_settings
import json

router = APIRouter(prefix="/api/star-stories", tags=["star_stories"])


class StarStoryCreate(BaseModel):
    tailored_resume_id: Optional[int] = None
    title: str
    story_theme: Optional[str] = None
    company_context: Optional[str] = None
    situation: str
    task: str
    action: str
    result: str
    key_themes: List[str] = []
    talking_points: List[str] = []
    experience_indices: List[int] = []


class StarStoryUpdate(BaseModel):
    title: Optional[str] = None
    story_theme: Optional[str] = None
    company_context: Optional[str] = None
    situation: Optional[str] = None
    task: Optional[str] = None
    action: Optional[str] = None
    result: Optional[str] = None
    key_themes: Optional[List[str]] = None
    talking_points: Optional[List[str]] = None


@router.post("/")
async def create_star_story(
    story: StarStoryCreate,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new STAR story and save it to the database.
    """
    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-ID header is required")

    try:
        # Create new STAR story
        new_story = StarStory(
            session_user_id=x_user_id,
            tailored_resume_id=story.tailored_resume_id,
            title=story.title,
            story_theme=story.story_theme,
            company_context=story.company_context,
            situation=story.situation,
            task=story.task,
            action=story.action,
            result=story.result,
            key_themes=story.key_themes,
            talking_points=story.talking_points,
            experience_indices=story.experience_indices,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        db.add(new_story)
        await db.commit()
        await db.refresh(new_story)

        print(f"✓ STAR story created with ID {new_story.id} for user {x_user_id}")

        return {
            "success": True,
            "story": new_story.to_dict()
        }

    except Exception as e:
        print(f"Failed to create STAR story: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create STAR story: {str(e)}"
        )


@router.get("/list")
async def list_star_stories(
    tailored_resume_id: Optional[int] = None,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    List all STAR stories for the current user (non-deleted).
    Optionally filter by tailored_resume_id.
    Returns stories sorted by most recent first.
    """
    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-ID header is required")

    try:
        # Build query conditions
        conditions = [
            StarStory.session_user_id == x_user_id,
            StarStory.is_deleted == False
        ]

        # Add optional tailored_resume_id filter
        if tailored_resume_id is not None:
            conditions.append(StarStory.tailored_resume_id == tailored_resume_id)

        # Fetch STAR stories for this user
        result = await db.execute(
            select(StarStory)
            .where(and_(*conditions))
            .order_by(StarStory.created_at.desc())
        )

        stories = result.scalars().all()

        return {
            "success": True,
            "count": len(stories),
            "stories": [story.to_dict() for story in stories]
        }

    except Exception as e:
        print(f"Failed to list STAR stories: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list STAR stories: {str(e)}"
        )


@router.get("/{story_id}")
async def get_star_story(
    story_id: int,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific STAR story by ID.
    Only returns story if it belongs to the current user.
    """
    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-ID header is required")

    try:
        result = await db.execute(
            select(StarStory).where(
                and_(
                    StarStory.id == story_id,
                    StarStory.session_user_id == x_user_id,
                    StarStory.is_deleted == False
                )
            )
        )
        story = result.scalar_one_or_none()

        if not story:
            raise HTTPException(status_code=404, detail="STAR story not found")

        return {
            "success": True,
            "story": story.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Failed to get STAR story: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get STAR story: {str(e)}"
        )


@router.put("/{story_id}")
async def update_star_story(
    story_id: int,
    story_update: StarStoryUpdate,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Update a STAR story.
    Only allows updating if story belongs to current user.
    """
    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-ID header is required")

    try:
        result = await db.execute(
            select(StarStory).where(
                and_(
                    StarStory.id == story_id,
                    StarStory.session_user_id == x_user_id,
                    StarStory.is_deleted == False
                )
            )
        )
        story = result.scalar_one_or_none()

        if not story:
            raise HTTPException(status_code=404, detail="STAR story not found")

        # Update fields if provided
        if story_update.title is not None:
            story.title = story_update.title
        if story_update.story_theme is not None:
            story.story_theme = story_update.story_theme
        if story_update.company_context is not None:
            story.company_context = story_update.company_context
        if story_update.situation is not None:
            story.situation = story_update.situation
        if story_update.task is not None:
            story.task = story_update.task
        if story_update.action is not None:
            story.action = story_update.action
        if story_update.result is not None:
            story.result = story_update.result
        if story_update.key_themes is not None:
            story.key_themes = story_update.key_themes
        if story_update.talking_points is not None:
            story.talking_points = story_update.talking_points

        story.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(story)

        print(f"✓ STAR story {story_id} updated")

        return {
            "success": True,
            "story": story.to_dict()
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Failed to update STAR story: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update STAR story: {str(e)}"
        )


@router.delete("/{story_id}")
async def delete_star_story(
    story_id: int,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Soft delete a STAR story.
    Only allows deletion if story belongs to current user.
    """
    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-ID header is required")

    try:
        result = await db.execute(
            select(StarStory).where(
                and_(
                    StarStory.id == story_id,
                    StarStory.session_user_id == x_user_id
                )
            )
        )
        story = result.scalar_one_or_none()

        if not story:
            raise HTTPException(status_code=404, detail="STAR story not found")

        # Soft delete
        story.is_deleted = True
        story.deleted_at = datetime.utcnow()

        await db.commit()

        print(f"✓ STAR story {story_id} deleted")

        return {
            "success": True,
            "message": "STAR story deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Failed to delete STAR story: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete STAR story: {str(e)}"
        )


# ============================================================================
# STAR STORY AI ANALYSIS ENDPOINTS
# These endpoints provide AI-powered analysis and improvement suggestions
# ============================================================================


@router.post("/{story_id}/analyze")
async def analyze_star_story(
    story_id: int,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Analyze a STAR story using AI and return scoring and feedback.

    Returns:
    - overall_score: 0-100
    - component_scores: Scores for situation, task, action, result
    - strengths: List of strengths
    - areas_for_improvement: List of areas to improve
    - impact_assessment: Assessment of story impact
    """
    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-ID header is required")

    try:
        # Fetch the story
        result = await db.execute(
            select(StarStory).where(
                and_(
                    StarStory.id == story_id,
                    StarStory.session_user_id == x_user_id,
                    StarStory.is_deleted == False
                )
            )
        )
        story = result.scalar_one_or_none()

        if not story:
            raise HTTPException(status_code=404, detail="STAR story not found")

        # Build story text for analysis
        story_text = f"""
TITLE: {story.title or 'Untitled'}
THEME: {story.story_theme or 'General'}

SITUATION:
{story.situation}

TASK:
{story.task}

ACTION:
{story.action}

RESULT:
{story.result}
"""

        # Analyze using OpenAI
        settings = get_settings()
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        prompt = f"""You are an expert interview coach. Analyze this STAR story and provide detailed feedback.

{story_text}

Analyze the story and return a JSON object with this exact structure:
{{
  "overall_score": 85,
  "component_scores": {{
    "situation": {{
      "score": 80,
      "feedback": "Clear context provided, but could add more specific details about the challenge."
    }},
    "task": {{
      "score": 85,
      "feedback": "Good clarity on responsibilities and objectives."
    }},
    "action": {{
      "score": 90,
      "feedback": "Excellent detail on specific actions taken."
    }},
    "result": {{
      "score": 82,
      "feedback": "Good outcomes mentioned, consider adding more metrics."
    }}
  }},
  "strengths": [
    "Clear narrative flow",
    "Good use of specific examples",
    "Demonstrates leadership"
  ],
  "areas_for_improvement": [
    "Add more quantifiable metrics to the result",
    "Include more context about team dynamics"
  ],
  "impact_assessment": {{
    "quantifiable_results": true,
    "leadership_demonstrated": true,
    "problem_solving_shown": true,
    "teamwork_highlighted": false
  }}
}}

Provide honest, constructive feedback that will help improve the story for interviews."""

        response = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert interview coach who helps candidates improve their STAR stories. Provide specific, actionable feedback."
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=2000
        )

        analysis = json.loads(response.choices[0].message.content)

        print(f"✓ Analyzed STAR story {story_id}, score: {analysis.get('overall_score', 0)}")

        return {
            "success": True,
            "data": analysis
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Failed to analyze STAR story: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze STAR story: {str(e)}"
        )


@router.post("/{story_id}/suggestions")
async def get_story_suggestions(
    story_id: int,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get AI-powered improvement suggestions for a STAR story.

    Returns:
    - improvement_tips: List of tips by component
    - alternative_framings: Different ways to frame the story
    - impact_enhancements: Ways to strengthen impact
    - keyword_recommendations: Keywords to include
    """
    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-ID header is required")

    try:
        # Fetch the story
        result = await db.execute(
            select(StarStory).where(
                and_(
                    StarStory.id == story_id,
                    StarStory.session_user_id == x_user_id,
                    StarStory.is_deleted == False
                )
            )
        )
        story = result.scalar_one_or_none()

        if not story:
            raise HTTPException(status_code=404, detail="STAR story not found")

        # Build story text
        story_text = f"""
TITLE: {story.title or 'Untitled'}
THEME: {story.story_theme or 'General'}

SITUATION: {story.situation}
TASK: {story.task}
ACTION: {story.action}
RESULT: {story.result}
"""

        # Get suggestions using OpenAI
        settings = get_settings()
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        prompt = f"""You are an expert interview coach. Provide specific improvement suggestions for this STAR story.

{story_text}

Return a JSON object with this exact structure:
{{
  "improvement_tips": [
    {{
      "component": "situation",
      "suggestion": "Add specific context about the business challenge",
      "reasoning": "This helps interviewers understand the stakes"
    }},
    {{
      "component": "task",
      "suggestion": "Clarify your specific role vs team responsibilities",
      "reasoning": "Interviewers want to know YOUR contributions"
    }},
    {{
      "component": "action",
      "suggestion": "Break down actions into numbered steps",
      "reasoning": "Makes the story easier to follow"
    }},
    {{
      "component": "result",
      "suggestion": "Add percentage or dollar impact",
      "reasoning": "Quantifiable results are more memorable"
    }}
  ],
  "alternative_framings": [
    {{
      "perspective": "Leadership Focus",
      "reframed_story": {{
        "situation": "As the lead on a critical project...",
        "result": "Resulting in team recognition and promotion..."
      }}
    }},
    {{
      "perspective": "Problem-Solving Focus",
      "reframed_story": {{
        "situation": "Facing an unprecedented technical challenge...",
        "result": "Creating a reusable solution now used across teams..."
      }}
    }}
  ],
  "impact_enhancements": [
    {{
      "type": "metrics",
      "enhancement": "Add specific percentages: 'improved efficiency by X%'"
    }},
    {{
      "type": "scope",
      "enhancement": "Mention team size or budget: 'led a team of X' or 'managed $X budget'"
    }}
  ],
  "keyword_recommendations": [
    "leadership",
    "collaboration",
    "innovation",
    "results-driven",
    "strategic thinking"
  ]
}}

Focus on practical, specific suggestions that will make the story more compelling in interviews."""

        response = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert interview coach providing specific, actionable suggestions to improve STAR stories."
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.5,
            max_tokens=2500
        )

        suggestions = json.loads(response.choices[0].message.content)

        print(f"✓ Generated suggestions for STAR story {story_id}")

        return {
            "success": True,
            "data": suggestions
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Failed to get story suggestions: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get story suggestions: {str(e)}"
        )


class StoryVariationsRequest(BaseModel):
    target_role: Optional[str] = None
    target_company: Optional[str] = None
    emphasis: Optional[str] = None  # "leadership", "technical", "collaboration", etc.


@router.post("/{story_id}/variations")
async def generate_story_variations(
    story_id: int,
    request: StoryVariationsRequest = None,
    x_user_id: str = Header(None, alias="X-User-ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate variations of a STAR story for different contexts.

    Returns:
    - variations: List of story variations
    - usage_tips: Tips for when to use each variation
    """
    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-ID header is required")

    try:
        # Fetch the story
        result = await db.execute(
            select(StarStory).where(
                and_(
                    StarStory.id == story_id,
                    StarStory.session_user_id == x_user_id,
                    StarStory.is_deleted == False
                )
            )
        )
        story = result.scalar_one_or_none()

        if not story:
            raise HTTPException(status_code=404, detail="STAR story not found")

        # Build story text
        story_text = f"""
TITLE: {story.title or 'Untitled'}
THEME: {story.story_theme or 'General'}

SITUATION: {story.situation}
TASK: {story.task}
ACTION: {story.action}
RESULT: {story.result}
"""

        # Build context for variations
        context = ""
        if request:
            if request.target_role:
                context += f"\nTarget Role: {request.target_role}"
            if request.target_company:
                context += f"\nTarget Company: {request.target_company}"
            if request.emphasis:
                context += f"\nEmphasis: {request.emphasis}"

        # Generate variations using OpenAI
        settings = get_settings()
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        prompt = f"""You are an expert interview coach. Generate 3 variations of this STAR story for different interview contexts.

ORIGINAL STORY:
{story_text}
{context if context else ''}

Create 3 different variations, each emphasizing different aspects. Return a JSON object:
{{
  "variations": [
    {{
      "name": "Leadership Version",
      "emphasis": "leadership",
      "when_to_use": "Use when asked about leadership, managing teams, or driving results",
      "story": {{
        "situation": "Reframed situation emphasizing leadership context...",
        "task": "Reframed task emphasizing leadership responsibility...",
        "action": "Reframed actions emphasizing leadership behaviors...",
        "result": "Reframed results emphasizing team/organizational impact..."
      }},
      "key_phrases": ["led the team", "drove consensus", "mentored colleagues"]
    }},
    {{
      "name": "Technical Excellence Version",
      "emphasis": "technical",
      "when_to_use": "Use when asked about technical skills, problem-solving, or innovation",
      "story": {{
        "situation": "Reframed situation emphasizing technical challenge...",
        "task": "Reframed task emphasizing technical requirements...",
        "action": "Reframed actions emphasizing technical approach...",
        "result": "Reframed results emphasizing technical outcomes..."
      }},
      "key_phrases": ["implemented solution", "optimized performance", "technical architecture"]
    }},
    {{
      "name": "Collaboration Version",
      "emphasis": "collaboration",
      "when_to_use": "Use when asked about teamwork, cross-functional work, or stakeholder management",
      "story": {{
        "situation": "Reframed situation emphasizing team dynamics...",
        "task": "Reframed task emphasizing collaborative goals...",
        "action": "Reframed actions emphasizing partnership...",
        "result": "Reframed results emphasizing shared success..."
      }},
      "key_phrases": ["partnered with", "aligned stakeholders", "collaborative effort"]
    }}
  ],
  "usage_tips": [
    "Listen carefully to the interview question to choose the right variation",
    "You can blend elements from different variations based on the specific question",
    "Practice each variation so you can switch naturally"
  ]
}}

Make each variation distinct and tailored for different types of interview questions."""

        response = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert interview coach who helps candidates adapt their STAR stories for different interview contexts."
                },
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=3500
        )

        variations = json.loads(response.choices[0].message.content)

        print(f"✓ Generated {len(variations.get('variations', []))} variations for STAR story {story_id}")

        return {
            "success": True,
            "data": variations
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Failed to generate story variations: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate story variations: {str(e)}"
        )
