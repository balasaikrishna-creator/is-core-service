from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.user_service import UserService
from app.schemas.user import UserResponse
from app.core.database import get_db

router = APIRouter()

@router.get("/{user_id}/preferences", response_model=dict)
async def get_preferences(user_id: int, db: AsyncSession = Depends(get_db)):
    user = await UserService.get_user_by_id(db, user_id)
    user_preferences = user.preferences if user and user.preferences else {}
    print("User Preferences:", user_preferences)  # Debugging line
    if user_preferences is None or user_preferences == {}:
        raise HTTPException(status_code=404, detail="No preferences found for user")
    return user_preferences
