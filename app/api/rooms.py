from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.room import RoomResponse
from app.services.hotel_service import HotelService
from app.core.database import get_db

router = APIRouter()

@router.get("/hotel/{hotel_id}", response_model=List[RoomResponse])
async def list_rooms(hotel_id: int, db: AsyncSession = Depends(get_db)):
    rooms_data = await HotelService.get_rooms_by_hotel(db, hotel_id)
    if rooms_data is None or len(rooms_data) == 0:
        raise HTTPException(status_code=404, detail="Rooms not found in Hotel")
    return rooms_data