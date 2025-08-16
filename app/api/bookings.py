from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.booking import BookingCreate, BookingResponse
from app.services.booking_service import BookingService
from app.core.database import get_db

router = APIRouter()

@router.post("/", response_model=BookingResponse)
async def book_room(booking_data: BookingCreate, db: AsyncSession = Depends(get_db)):
    booking = await BookingService.create_booking(db, booking_data)
    if not booking:
        raise HTTPException(status_code=400, detail="Booking failed")
    return booking
