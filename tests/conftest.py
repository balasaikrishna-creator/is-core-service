import pytest
import uuid
from sqlalchemy import delete
from app.models.database import User, Base
from app.core.database import get_db
from app.core.config import settings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import pytest_asyncio

# Use a separate test database URL if available, else fallback to main
TEST_DATABASE_URL = getattr(settings, "TEST_DATABASE_URL", settings.DATABASE_URL)

# Create a new async engine and session for testing
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    future=True
)
TestingSessionLocal = sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Set up and tear down the test database at the session level
@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    # Create all tables at the start
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Drop all tables at the end
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

# Async database session fixture for each test
@pytest_asyncio.fixture
async def db_session():
    async with TestingSessionLocal() as session:
        yield session

# Unique user fixture: provides payload and cleanup
@pytest_asyncio.fixture
async def unique_user(db_session):
    email = f"testuser_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "email": email,
        "first_name": "Test",
        "last_name": "User",
        "password": "SecurePass123"
    }
    yield payload
    # Cleanup user after test
    await db_session.execute(delete(User).where(User.email == email))
    await db_session.commit()
