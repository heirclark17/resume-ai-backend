from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel
from typing import List, Optional
from app.database import get_db
from app.models.star_story import StarStory
from datetime import datetime

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
