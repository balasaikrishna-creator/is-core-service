from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.room import RoomResponse, RoomCreate
from app.services.room_service import RoomService
from app.core.database import get_db

router = APIRouter()

@router.get("/hotel/{hotel_id}", response_model=List[RoomResponse])
async def list_rooms(hotel_id: int, db: AsyncSession = Depends(get_db)):
    rooms_data = await RoomService.get_rooms_by_hotel(db, hotel_id)
    if rooms_data is None or len(rooms_data) == 0:
        raise HTTPException(status_code=404, detail="Rooms not found in Hotel")
    return rooms_data

@router.post("/hotel/{hotel_id}", response_model=RoomResponse)
async def add_rooms(room: RoomCreate, hotel_id: int, db: AsyncSession = Depends(get_db)):
    rooms_data = await RoomService.add_rooms_by_hotel_id(db, room, hotel_id)
    if rooms_data is None:
        raise HTTPException(status_code=404, detail="Rooms not found in Hotel")
    return rooms_data

@router.delete("/hotel/{hotel_id}/room/{room_id}", response_model=RoomResponse)
async def delete_rooms(hotel_id: int,room_id: int, db: AsyncSession = Depends(get_db)):
    rooms_data = await RoomService.delete_rooms_by_room_id(db, hotel_id, room_id)
    if rooms_data is None:
        raise HTTPException(status_code=404, detail="Rooms not found in Hotel")
    return rooms_data

@router.put("/hotel/{hotel_id}/room/{room_id}", response_model=RoomResponse)
async def update_rooms(room: RoomCreate, hotel_id: int, room_id: int, db: AsyncSession = Depends(get_db)):
    rooms_data = await RoomService.update_rooms_by_room_id(db, room, hotel_id, room_id)
    if rooms_data is None:
        raise HTTPException(status_code=404, detail="Rooms not found in Hotel")
    return rooms_data