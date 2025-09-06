from fastapi import APIRouter, Depends, Query
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.hotel import HotelResponse
from app.services.hotel_service import HotelService
from app.core.database import get_db
from fastapi import HTTPException

router = APIRouter()

@router.get("/search", response_model=List[HotelResponse])
async def search_hotels(
    city: str = Query(None),
    min_price: float = Query(None),
    max_price: float = Query(None),
    rating: float = Query(None),
    db: AsyncSession = Depends(get_db)
):
    data = await HotelService.search_hotels(db, city, min_price, max_price, rating)
    if data is None:
        raise HTTPException(status_code=404, detail="No Hotel data found")
    return data

@router.get("/{hotel_id}", response_model=HotelResponse)
async def get_hotel(hotel_id: int, db: AsyncSession = Depends(get_db)):
    hotel = await HotelService.get_hotel_by_id(db, hotel_id)
    if hotel is None:
        raise HTTPException(status_code=404, detail="Hotel not found")
    return hotel

