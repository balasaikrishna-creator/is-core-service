from fastapi import APIRouter, Depends
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.room import RoomResponse
from app.services.hotel_service import HotelService
from app.core.database import get_db

router = APIRouter()

@router.get("/hotel/{hotel_id}", response_model=List[RoomResponse])
async def list_rooms(hotel_id: int, db: AsyncSession = Depends(get_db)):
    return await HotelService.get_rooms_by_hotel(db, hotel_id)
