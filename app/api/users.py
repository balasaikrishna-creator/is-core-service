from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.user_service import UserService
from app.schemas.user import UserResponse
from app.core.database import get_db

router = APIRouter()

@router.get("/{user_id}/preferences", response_model=dict)
async def get_preferences(user_id: int, db: AsyncSession = Depends(get_db)):
    user = await UserService.get_user_by_id(db, user_id)
    return user.preferences
