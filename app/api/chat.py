import traceback

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.chat import (
    ChatMessageRequest,
    ChatResponse,
    ChatSessionResponse
)
from app.services.ai_service import AIService

router = APIRouter()


@router.post("/message", response_model=ChatResponse)
async def send_message(
        request: ChatMessageRequest,
        db: AsyncSession = Depends(get_db)
):
    """
    Send a message to the AI assistant and get a response
    """
    ai_service = AIService()
    try:
        response = await ai_service.process_message(db, request)
        return response
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing message: {str(e)}"
        )


@router.get("/session/{session_id}", response_model=ChatSessionResponse)
async def get_session(
        session_id: str,
        db: AsyncSession = Depends(get_db)
):
    """
    Get chat session history
    """
    ai_service = AIService()
    session = await ai_service.get_session_history(db, session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    return ChatSessionResponse(
        session_id=session.session_id,
        user_id=session.user_id,
        messages=session.messages or [],
        created_at=session.created_at,
        updated_at=session.updated_at
    )


@router.delete("/session/{session_id}")
async def delete_session(
        session_id: str,
        db: AsyncSession = Depends(get_db)
):
    """
    Delete a chat session
    """
    ai_service = AIService()
    session = await ai_service.get_session_history(db, session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    await db.delete(session)
    await db.commit()

    return {"message": "Session deleted successfully"}
