from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.user import User, UserResponse
from app.services.user_service import UserService

router = APIRouter()

@router.get("/{user_id}/preferences", response_model=dict)
async def get_preferences(user_id: int, db: AsyncSession = Depends(get_db)):
    user = await UserService.get_user_by_id(db, user_id)
    user_preferences = user.preferences if user and user.preferences else {}
    if user_preferences is None or user_preferences == {}:
        raise HTTPException(status_code=404, detail="No preferences found for user")
    return user_preferences

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, user_data: User, db: AsyncSession = Depends(get_db)):
    user = await UserService.update_user_info(db, user_id, user_data)
    if user is None:
        raise HTTPException(status_code=404, detail="No preferences found for user")
    return user

@router.delete("/{user_id}", response_model=UserResponse)
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db)):
    user = await UserService.delete_user_info(db, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="No preferences found for user")
    return user
