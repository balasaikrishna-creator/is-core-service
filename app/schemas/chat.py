from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class MessageBase(BaseModel):
    role: str = Field(..., description="Role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")
    timestamp: Optional[datetime] = None


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    session_id: Optional[str] = None
    user_id: Optional[int] = None


class HotelRecommendation(BaseModel):
    id: int
    name: str
    city: str
    rating: float
    price_range: str
    description: Optional[str] = None
    amenities: Optional[List[str]] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    recommendations: List[HotelRecommendation] = []
    conversation_context: Optional[Dict[str, Any]] = None


class ChatSessionResponse(BaseModel):
    session_id: str
    user_id: Optional[int]
    messages: List[MessageBase]
    created_at: datetime
    updated_at: datetime
