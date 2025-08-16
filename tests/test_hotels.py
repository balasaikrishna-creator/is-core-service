import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_search_hotel():
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.get("/api/hotels/search", params={"city":"New York"})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
