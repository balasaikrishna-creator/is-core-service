from pydantic import BaseModel
from typing import List, Optional
from datetime import date

class HotelBase(BaseModel):
    name: str
    description: Optional[str]
    city: str
    country: str
    price_min: float
    price_max: float
    rating: float
    amenities: List[str]
    images: List[str]

class HotelCreate(HotelBase):
    name: str
    description: Optional[str]
    city: str
    country: str
    price_min: float
    price_max: float
    rating: float
    amenities: List[str]
    images: List[str]

class HotelResponse(HotelBase):
    id: int

    class Config:
        from_attributes = True
