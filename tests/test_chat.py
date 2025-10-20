import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_send_chat_message():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/chat/message",
            json={"message": "I'm looking for a hotel in New York with a pool", "user_id": 1}
        )
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "session_id" in data
        assert "recommendations" in data

@pytest.mark.asyncio
async def test_get_session_history():
    async with AsyncClient(app=app, base_url="http://test") as client:
        # First, send a message to create session
        create_response = await client.post(
            "/api/chat/message",
            json={"message": "Hello"}
        )
        session_id = create_response.json()["session_id"]

        # Get session history
        response = await client.get(f"/api/chat/session/{session_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert len(data["messages"]) >= 2  # User + Assistant
