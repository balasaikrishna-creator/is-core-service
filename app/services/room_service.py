from sqlalchemy import select, and_, delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Room
from app.schemas.room import RoomCreate


class RoomService:
    @staticmethod
    async def get_rooms_by_hotel(db: AsyncSession, hotel_id: int):
        query = select(Room).where(Room.hotel_id == hotel_id)
        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def add_rooms_by_hotel_id(db: AsyncSession, room_data: RoomCreate, hotel_id: int):
        new_room = Room(**room_data.dict(), hotel_id=hotel_id)
        db.add(new_room)
        await db.commit()
        await db.refresh(new_room)
        return new_room

    @staticmethod
    async def delete_rooms_by_room_id(db: AsyncSession, hotel_id: int, room_id: int):
        query = delete(Room).where(and_(Room.hotel_id == hotel_id, Room.id == room_id)).returning(Room)
        result = await db.execute(query)
        await db.commit()
        return result.scalar_one_or_none()

    @staticmethod
    async def update_rooms_by_room_id(db: AsyncSession, room_data: RoomCreate, hotel_id: int, room_id: int):
        query = update(Room).where(and_(Room.hotel_id == hotel_id, Room.id == room_id)).values(**room_data.dict()).returning(Room)
        result = await db.execute(query)
        await db.commit()
        updated_room = result.scalar_one_or_none()
        return updated_room