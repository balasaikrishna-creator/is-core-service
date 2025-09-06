from dotenv import load_dotenv

load_dotenv()

import asyncio
from app.core.database import AsyncSessionLocal
from app.models.database import Hotel, Room

async def seed():
    async with AsyncSessionLocal() as session:
        # Add hotels first
        hotels = [
            Hotel(name="Grand Plaza", country="USA", city="New York", price_min=200, price_max=500, amenities=["WiFi","Pool"], rating=4.5),
            Hotel(name="Cozy Inn", country="USA", city="Los Angeles", price_min=80, price_max=150, amenities=["WiFi"], rating=3.8),
        ]
        session.add_all(hotels)
        await session.flush()  # Flush to assign PK ids without commit

        # Now create rooms with correct hotel IDs
        rooms = [
            Room(hotel_id=hotels[0].id, room_type="Deluxe", price=250, amenities=["WiFi", "TV"]),
            Room(hotel_id=hotels[0].id, room_type="Suite", price=400, amenities=["WiFi", "TV", "Mini-Bar"]),
            Room(hotel_id=hotels[1].id, room_type="Standard", price=90, amenities=["WiFi"]),
        ]
        session.add_all(rooms)

        await session.commit()  # Commit all changes

if __name__ == "__main__":
    asyncio.run(seed())
