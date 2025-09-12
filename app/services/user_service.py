# File: app/services/user_service.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from passlib.context import CryptContext

from app.models.database import User
from app.schemas.user import UserCreate

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserService:
    @staticmethod
    async def create_user(db: AsyncSession, user_data: UserCreate) -> User:
        hashed_password = pwd_context.hash(user_data.password)
        new_user = User(
            email=user_data.email,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            password_hash=hashed_password
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return new_user

    @staticmethod
    async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user and pwd_context.verify(password, user.password_hash):
            return user
        return None

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_email(db, email: str):
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_user_info(db: AsyncSession, user_id: int, user_data: User) -> User | None:
        query = update(User).where(User.id == user_id).values(**user_data.dict()).returning(User)
        result = await db.execute(query)
        await db.commit()
        return result.scalar_one_or_none()

    @staticmethod
    async def delete_user_info(db: AsyncSession, user_id: int) -> User | None:
        query = delete(User).where(User.id == user_id).returning(User)
        result = await db.execute(query)
        await db.commit()
        return result.scalar_one_or_none()
