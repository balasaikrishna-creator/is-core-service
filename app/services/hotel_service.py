from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, delete, update
from app.models.database import Hotel, Room
from app.schemas.hotel import HotelResponse, HotelCreate


class HotelService:
    @staticmethod
    async def search_hotels(db: AsyncSession, city: str, min_price: float = None, max_price: float = None, rating: float = None):
        query = select(Hotel)
        conditions = []
        if city: conditions.append(Hotel.city.ilike(f"%{city}%"))
        if min_price: conditions.append(Hotel.price_min >= min_price)
        if max_price: conditions.append(Hotel.price_max <= max_price)
        if rating: conditions.append(Hotel.rating >= rating)
        query = query.where(and_(*conditions)).limit(20)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_hotel_by_id(db: AsyncSession, hotel_id: int):
        query = select(Hotel).where(Hotel.id == hotel_id)
        result = await db.execute(query)
        hotel_obj = result.scalar_one_or_none()
        return hotel_obj

    @staticmethod
    async def create_hotel(db: AsyncSession, hotel_data: HotelCreate):
        new_hotel = Hotel(**hotel_data.dict())
        db.add(new_hotel)
        await db.commit()
        await db.refresh(new_hotel)
        return new_hotel

    @staticmethod
    async def delete_hotel_by_id(db: AsyncSession, hotel_id: int):
        query = delete(Hotel).where(Hotel.id == hotel_id).returning(Hotel)
        result = await db.execute(query)
        await db.commit()
        return result.scalar_one_or_none()

    @staticmethod
    async def update_hotel_by_id(db: AsyncSession, hotel_data: HotelCreate, hotel_id: int):
        query = update(Hotel).where(Hotel.id == hotel_id).values(**hotel_data.dict()).returning(Hotel)
        result = await db.execute(query)
        await db.commit()
        updated_hotel = result.scalar_one_or_none()
        return updated_hotel