from pydantic import BaseModel
from typing import List

class RoomBase(BaseModel):
    room_type: str
    description: str
    price: float
    amenities: List[str]

class RoomResponse(RoomBase):
    id: int
    available: bool

    class Config:
        from_attributes = True
