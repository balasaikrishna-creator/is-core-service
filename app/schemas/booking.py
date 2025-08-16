from pydantic import BaseModel
from datetime import date

class BookingCreate(BaseModel):
    user_id: int
    hotel_id: int
    room_id: int
    check_in: date
    check_out: date
    guests: int

class BookingResponse(BookingCreate):
    id: int
    status: str

    class Config:
        from_attributes = True
