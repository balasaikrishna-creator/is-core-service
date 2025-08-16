import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_register_and_login(unique_user):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Test user registration with unique user payload
        register_payload = unique_user
        register_response = await client.post("/api/auth/register", json=register_payload)
        assert register_response.status_code == 200
        register_data = register_response.json()
        assert register_data["email"] == register_payload["email"]
        assert "id" in register_data

        # Test user login with dynamic email and password from registration
        login_payload = {
            "email": register_payload["email"],
            "password": register_payload["password"]
        }
        login_response = await client.post("/api/auth/login", json=login_payload)
        assert login_response.status_code == 200
        login_data = login_response.json()
        assert "access_token" in login_data
        assert login_data["token_type"] == "bearer"

        # Test accessing protected profile route with Bearer token
        token = login_data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        profile_response = await client.get("/api/auth/profile", headers=headers)
        assert profile_response.status_code == 200
        profile_data = profile_response.json()
        assert profile_data["email"] == register_payload["email"]
        assert profile_data["first_name"] == register_payload["first_name"]
        assert profile_data["last_name"] == register_payload["last_name"]
