from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import Booking
from app.schemas.booking import BookingCreate

class BookingService:
    @staticmethod
    async def create_booking(db: AsyncSession, data: BookingCreate):
        booking = Booking(**data.dict(), status="pending")
        db.add(booking)
        await db.commit()
        await db.refresh(booking)
        return booking
