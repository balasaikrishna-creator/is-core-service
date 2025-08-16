import asyncio
from app.core.database import AsyncSessionLocal
from app.models.database import Hotel, Room

async def seed():
    async with AsyncSessionLocal() as session:
        session.add_all([
            Hotel(name="Grand Plaza", city="New York", price_min=200, price_max=500, amenities=["WiFi","Pool"], rating=4.5),
            Hotel(name="Cozy Inn", city="Los Angeles", price_min=80, price_max=150, amenities=["WiFi"], rating=3.8),
        ])
        session.add_all([
            Room(hotel_id=1, room_type="Deluxe", price=250, amenities=["WiFi", "TV"]),
            Room(hotel_id=1, room_type="Suite", price=400, amenities=["WiFi", "TV", "Mini-Bar"]),
            Room(hotel_id=2, room_type="Standard", price=90, amenities=["WiFi"])
        ])
        await session.commit()

if __name__ == "__main__":
    asyncio.run(seed())
