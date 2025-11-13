from dotenv import load_dotenv
load_dotenv()

import asyncio
from sqlalchemy import select, and_, func
from app.core.database import AsyncSessionLocal
from app.models.database import Hotel, Room, User


async def get_or_create_hotel(session, name: str, city: str, country: str, price_min: float, price_max: float, amenities, rating: float):
    q = (
        select(Hotel)
        .where(func.lower(Hotel.name) == name.lower())
        .where(func.lower(Hotel.city) == city.lower())
    )
    res = await session.execute(q)
    existing = res.scalars().first()
    if existing:
        return existing
    h = Hotel(name=name, city=city, country=country, price_min=price_min, price_max=price_max, amenities=amenities, rating=rating)
    session.add(h)
    await session.flush()
    return h


async def get_or_create_room(session, hotel_id: int, room_type: str, price: float, amenities):
    q = (
        select(Room)
        .where(and_(Room.hotel_id == hotel_id, func.lower(Room.room_type) == room_type.lower(), Room.price == price))
    )
    res = await session.execute(q)
    existing = res.scalars().first()
    if existing:
        return existing
    r = Room(hotel_id=hotel_id, room_type=room_type, price=price, amenities=amenities)
    session.add(r)
    await session.flush()
    return r


async def get_or_create_user(session, email: str, first_name: str, last_name: str, password_hash: str, id: int | None = None):
    q = select(User).where(func.lower(User.email) == email.lower())
    res = await session.execute(q)
    existing = res.scalars().first()
    if existing:
        return existing
    u = User(email=email, first_name=first_name, last_name=last_name, password_hash=password_hash)
    if id is not None:
        try:
            # Only set id if free; else let DB assign
            u.id = id
        except Exception:
            pass
    session.add(u)
    await session.flush()
    return u


async def seed():
    async with AsyncSessionLocal() as session:
        # Hotels (idempotent)
        h1 = await get_or_create_hotel(session, name="Grand Plaza", country="USA", city="New York", price_min=200, price_max=500, amenities=["WiFi", "Pool"], rating=4.5)
        h2 = await get_or_create_hotel(session, name="Cozy Inn", country="USA", city="Los Angeles", price_min=80, price_max=150, amenities=["WiFi"], rating=3.8)

        # Rooms (idempotent)
        await get_or_create_room(session, hotel_id=h1.id, room_type="Deluxe", price=250, amenities=["WiFi", "TV"])
        await get_or_create_room(session, hotel_id=h1.id, room_type="Suite", price=400, amenities=["WiFi", "TV", "Mini-Bar"])
        await get_or_create_room(session, hotel_id=h2.id, room_type="Standard", price=90, amenities=["WiFi"])

        # User (idempotent)
        await get_or_create_user(session, email="bala@gmail.com", first_name='bala', last_name='gontla', password_hash='bala', id=1)

        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
