import json
import re
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
import random


import google.generativeai as genai
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.database import ChatSession, Hotel
from app.schemas.chat import ChatMessageRequest, ChatResponse, HotelRecommendation

class AIService:
    def __init__(self):
        genai.configure(api_key=settings.GOOGLE_GEMINI_API_KEY)
        self.model = genai.GenerativeModel("models/gemini-2.5-flash")
        # Dynamic templates
        self.openings = [
            "Good news! I found some hotels in {location} with pools:",
            "Here are a few great pool-equipped hotels in {location}:",
            "I’ve got some poolside hotel options for you in {location}:",
            "Take a look at these hotels in {location} that feature pools:"
        ]
        self.closings = [
            "Would you like more details on any of these?",
            "Let me know if you want to refine your search or see more info.",
            "Interested in booking one of these or exploring further options?",
            "Feel free to ask for more specifics or more choices!"
        ]

    async def process_message(
        self,
        db: AsyncSession,
        request: ChatMessageRequest
    ) -> ChatResponse:
        # 1. Session management
        session_id = request.session_id or str(uuid.uuid4())
        chat_session = await self._get_or_create_session(db, session_id, request.user_id)

        # 2. Context extraction
        context = await self._extract_context(db, request.message, chat_session)

        # 3. Get recommendations
        recommendations = await self._get_recommendations(db, context)

        # 4. If recommendations exist, build and return direct response
        if recommendations:
            # Choose dynamic opening and closing
            opening = random.choice(self.openings).format(location=context.get('location'))
            closing = random.choice(self.closings)

            # Build recommendation text
            rec_text = opening + "\n\n"
            for h in recommendations:
                desc = h.description or "No description available."
                rec_text += (
                    f"• {h.name} ({h.rating}★) – {h.price_range}\n"
                    f"  {desc}\n\n"
                )
            rec_text += closing

            return ChatResponse(
                response=rec_text,
                session_id=session_id,
                recommendations=recommendations,
                conversation_context=context
            )

        # 5. Otherwise, fall back to conversational AI
        messages = self._build_gpt_messages(chat_session, request.message, context)
        gpt_response = await self._call_gemini(messages)

        # 6. Update session with new interaction
        await self._update_session(db, chat_session, request.message, gpt_response, context)

        return ChatResponse(
            response=gpt_response,
            session_id=session_id,
            recommendations=recommendations,
            conversation_context=context
        )

    async def _call_gemini(self, messages: List[Dict[str, str]]) -> str:
        """Call Google Gemini and return generated text."""
        try:
            prompt = self._convert_messages_to_prompt(messages)
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"Google Gemini API error: {e}")
            return "I'm having trouble processing your request right now. Please try again in a moment."

    def _convert_messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Flatten OpenAI-style messages into a single Gemini prompt."""
        prompt_parts = []
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            if role == 'system':
                prompt_parts.append(f"Instructions: {content}")
            elif role == 'user':
                prompt_parts.append(f"User: {content}")
            elif role == 'assistant':
                prompt_parts.append(f"Assistant: {content}")
        return "\n\n".join(prompt_parts)

    async def _get_or_create_session(
        self,
        db: AsyncSession,
        session_id: str,
        user_id: Optional[int]
    ) -> ChatSession:
        """Retrieve or create a chat session record."""
        result = await db.execute(select(ChatSession).where(ChatSession.session_id == session_id))
        session = result.scalar_one_or_none()
        if not session:
            session = ChatSession(
                session_id=session_id,
                user_id=user_id,
                messages=[],
                context={}
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)
        return session

    async def _extract_context(
        self,
        db: AsyncSession,
        message: str,
        chat_session: ChatSession
    ) -> Dict[str, Any]:
        """Extract location, dates, preferences, and guests from the user message."""
        context = chat_session.context or {}
        location = self._extract_location(message)
        if location:
            context['location'] = location
        dates = self._extract_dates(message)
        if dates:
            context.update(dates)
        preferences = self._extract_preferences(message)
        if preferences:
            context['preferences'] = preferences
        guests = self._extract_guest_count(message)
        if guests:
            context['guests'] = guests
        return context

    def _extract_location(self, message: str) -> Optional[str]:
        patterns = [
            r"(?:in|at|near|around)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            r"(?:visit|visiting|go to|going to|trip to)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            r"hotels? (?:in|at|near)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"
        ]
        for pattern in patterns:
            m = re.search(pattern, message)
            if m:
                return m.group(1)
        known = ["New York","Los Angeles","Chicago","Miami","Seattle",
                 "San Francisco","Boston","Las Vegas","Orlando","Denver"]
        ml = message.lower()
        for city in known:
            if city.lower() in ml:
                return city
        return None

    def _extract_dates(self, message: str) -> Dict[str, Any]:
        dates = {}
        ml = message.lower()
        if "check in" in ml or "checking in" in ml:
            dates['has_checkin'] = True
        if "check out" in ml or "checking out" in ml:
            dates['has_checkout'] = True
        return dates

    def _extract_preferences(self, message: str) -> Dict[str, Any]:
        prefs = {}
        ml = message.lower()
        if any(w in ml for w in ['cheap','budget','affordable','inexpensive']):
            prefs['budget'] = 'low'
        elif any(w in ml for w in ['luxury','premium','high-end','expensive']):
            prefs['budget'] = 'high'
        elif any(w in ml for w in ['mid-range','moderate']):
            prefs['budget'] = 'medium'
        amenities = []
        keys = {
            'pool':['pool','swimming'],
            'wifi':['wifi','internet','wireless'],
            'gym':['gym','fitness','workout'],
            'spa':['spa','massage','wellness'],
            'restaurant':['restaurant','dining','food'],
            'parking':['parking','garage'],
            'pet':['pet','dog','cat']
        }
        for amen, kws in keys.items():
            if any(k in ml for k in kws):
                amenities.append(amen)
        if amenities:
            prefs['amenities'] = amenities
        return prefs

    def _extract_guest_count(self, message: str) -> Optional[int]:
        for pat in [r"(\d+)\s+(?:guest|people|person|adult)", r"(?:for|with)\s+(\d+)"]:
            m = re.search(pat, message.lower())
            if m:
                return int(m.group(1))
        return None

    async def _get_recommendations(
            self,
            db: AsyncSession,
            context: Dict[str, Any]
    ) -> List[HotelRecommendation]:
        if not context.get('location'):
            return []

        query = select(Hotel).where(
            Hotel.city.ilike(f"%{context['location']}%")
        )

        # Budget filter omitted for brevity...

        # Apply amenity filters using .any()
        for amen in context.get('preferences', {}).get('amenities', []):
            amen_title = amen.title()
            query = query.where(Hotel.amenities.any(amen_title))

        result = await db.execute(query)
        hotels = result.scalars().all()

        return [
            HotelRecommendation(
                id=h.id,
                name=h.name,
                city=h.city,
                rating=float(h.rating or 0),
                price_range=f"${h.price_min}-{h.price_max}",
                description=h.description,
                amenities=h.amenities
            )
            for h in hotels
        ]

    def _build_gpt_messages(
        self,
        chat_session: ChatSession,
        new_message: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        system_prompt = (
            "You are a helpful travel assistant for IntelliStay, "
            "a hotel booking platform. Help users find perfect accommodations."
        )
        msgs = [{"role": "system", "content": system_prompt}]
        if context:
            msgs.append({"role": "system", "content": f"Context: {json.dumps(context)}"})
        for msg in (chat_session.messages or [])[-10:]:
            msgs.append({"role": msg.get('role', 'user'), "content": msg.get('content', '')})
        msgs.append({"role": "user", "content": new_message})
        return msgs

    async def _update_session(
        self,
        db: AsyncSession,
        chat_session: ChatSession,
        user_message: str,
        assistant_response: str,
        context: Dict[str, Any]
    ):
        """Append messages to session and commit."""
        msgs = chat_session.messages or []
        msgs.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.utcnow().isoformat()
        })
        msgs.append({
            "role": "assistant",
            "content": assistant_response,
            "timestamp": datetime.utcnow().isoformat()
        })
        stmt = update(ChatSession).where(
            ChatSession.session_id == chat_session.session_id
        ).values(
            messages=msgs,
            context=context,
            updated_at=datetime.utcnow()
        )
        await db.execute(stmt)
        await db.commit()

    async def get_session_history(
        self,
        db: AsyncSession,
        session_id: str
    ) -> Optional[ChatSession]:
        """Retrieve full chat history."""
        result = await db.execute(
            select(ChatSession).where(ChatSession.session_id == session_id)
        )
        return result.scalar_one_or_none()
