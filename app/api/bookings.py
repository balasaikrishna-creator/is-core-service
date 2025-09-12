from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.booking import BookingCreate, BookingResponse, BookingUpdate
from app.services.booking_service import BookingService

router = APIRouter()

@router.post("/", response_model=BookingResponse)
async def book_room(booking_data: BookingCreate, db: AsyncSession = Depends(get_db)):
    booking = await BookingService.create_booking(db, booking_data)
    if not booking:
        raise HTTPException(status_code=400, detail="Booking failed")
    return booking

@router.get("/user/{user_id}")
async def get_bookings(user_id: int, db: AsyncSession = Depends(get_db)):
    booking = await BookingService.get_booking_by_user_id(db, user_id)
    if not booking:
        raise HTTPException(status_code=400, detail="No Bookings found")
    return booking

@router.put("/{booking_id}", response_model=BookingResponse)
async def update_booking(booking_data: BookingUpdate, booking_id: int, db: AsyncSession = Depends(get_db)):
    booking = await BookingService.update_booking_by_booking_id(db, booking_data, booking_id)
    if not booking:
        raise HTTPException(status_code=400, detail="Update Booking failed")
    return booking

@router.delete("/{booking_id}", response_model=BookingResponse)
async def delete_booking(booking_id: int, db: AsyncSession = Depends(get_db)):
    booking = await BookingService.delete_booking_by_booking_id(db, booking_id)
    if not booking:
        raise HTTPException(status_code=400, detail="Delete Booking failed")
    return booking
