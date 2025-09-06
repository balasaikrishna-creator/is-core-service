# File: app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.testing.suite.test_reflection import users

from app.core.config import settings
from app.core.database import init_db
from app.api import auth, hotels, bookings, rooms, users, payments

# chat, integrations)

app = FastAPI(
    title="IntelliStay API",
    version="1.0.0"
)

# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    # Automatically create database tables
    await init_db()

# Include your routers
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(hotels.router, prefix="/api/hotels", tags=["Hotels"])
app.include_router(bookings.router, prefix="/api/bookings", tags=["Bookings"])
app.include_router(rooms.router, prefix="/api/rooms", tags=["Rooms"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(payments.router, prefix="/api/payments", tags=["Payments"])
# app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
# app.include_router(integrations.router, prefix="/api/integrations", tags=["Integrations"])
