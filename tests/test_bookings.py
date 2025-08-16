import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_booking():
    async with AsyncClient(app=app, base_url="http://test") as client:
        payload = {
            "user_id": 1,
            "hotel_id": 1,
            "room_id": 1,
            "check_in":"2025-09-01",
            "check_out":"2025-09-03",
            "guests":2
        }
        resp = await client.post("/api/bookings/", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "pending"
