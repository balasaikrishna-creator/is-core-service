from typing import Optional

from pydantic import BaseModel
from datetime import date

class BookingCreate(BaseModel):
    user_id: int
    hotel_id: int
    room_id: int
    check_in: date
    check_out: date
    guests: int
    status: str

class BookingResponse(BookingCreate):
    id: int
    status: str
    
class BookingUpdate(BaseModel):
    check_in: Optional[date] = None
    check_out: Optional[date] = None
    guests: Optional[int] = None
    status: Optional[str] = 'Pending'

    class Config:
        from_attributes = True
