from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import Booking, Hotel, Room
from app.schemas.booking import BookingCreate, BookingUpdate
from sqlalchemy import select, and_, delete, update, text


class BookingService:
    @staticmethod
    async def create_booking(db: AsyncSession, data: BookingCreate):
        booking = Booking(**data.dict())
        db.add(booking)
        await db.commit()
        await db.refresh(booking)
        return booking

    @staticmethod
    async def get_booking_by_user_id(db: AsyncSession, user_id: int):
        query = (select(
                Booking.id, Booking.user_id, Booking.hotel_id, Booking.room_id, Booking.check_in, Booking.check_out,
                Booking.guests, Booking.status,
                Hotel.name, Hotel.description.label("hotel_description"), Hotel.city, Hotel.country, Hotel.price_min,
                Hotel.price_max, Hotel.rating, Hotel.amenities.label("hotel_amenities"), Hotel.images,
                Room.room_type, Room.description.label("room_description"), Room.price,
                Room.amenities.label("room_amenities"), Room.available
                )
                .join(Hotel, Booking.hotel_id == Hotel.id)
                .join(Room, Booking.room_id == Room.id)
                .where(Booking.user_id == user_id))
        result = await db.execute(query)
        bookings = result.mappings().all()
        return bookings

    @staticmethod
    async def update_booking_by_booking_id(db: AsyncSession, booking_data: BookingUpdate, booking_id: int):
        query = update(Booking).where(Booking.id == booking_id).values(**booking_data.dict()).returning(Booking)
        result = await db.execute(query)
        await db.commit()
        updated_booking = result.scalar_one_or_none()
        return updated_booking

    @staticmethod
    async def delete_booking_by_booking_id(db: AsyncSession, booking_id: int):
        query = delete(Booking).where(Booking.id == booking_id).returning(Booking)
        result = await db.execute(query)
        await db.commit()
        return result.scalar_one_or_none()
