from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from app.database import get_db
from app.models.user import User
from app.middleware.auth import get_current_user

router = APIRouter()

class UserCreate(BaseModel):
    email: EmailStr
    username: str

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    api_key: str
    created_at: str

@router.post("/register", response_model=UserResponse)
async def register_user(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user and get an API key

    Returns:
        - API key for authentication (save this securely!)
    """
    # Check if email already exists
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Check if username already exists
    result = await db.execute(
        select(User).where(User.username == user_data.username)
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(status_code=400, detail="Username already taken")

    # Create new user with hashed API key
    user = User.create_user(
        email=user_data.email,
        username=user_data.username
    )

    # Get plaintext key before it's lost (only available during creation)
    plaintext_api_key = user._plaintext_api_key

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "api_key": plaintext_api_key,  # Return plaintext key ONCE (hashed in DB)
        "created_at": user.created_at.isoformat(),
        "warning": "Save this API key - it won't be shown again!"
    }


@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current authenticated user info (requires authentication)"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "created_at": current_user.created_at.isoformat(),
        "is_active": current_user.is_active
    }
