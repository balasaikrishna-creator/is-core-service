from pydantic import BaseModel
from typing import List, Optional


class RoomBase(BaseModel):
    room_type: str
    description: Optional[str] = None
    price: float
    amenities: List[str]

class RoomResponse(RoomBase):
    id: int
    available: bool
    hotel_id: int

class RoomCreate(BaseModel):
    room_type: str
    description: Optional[str] = None
    price: float
    amenities: List[str]
    available: bool

    class Config:
        from_attributes = True
