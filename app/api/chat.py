# python
import json
import random
import re
import uuid
from datetime import datetime, date
from typing import List, Dict, Any, Tuple, Optional

import google.generativeai as genai
from sqlalchemy import select, update, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.database import ChatSession, Hotel, Room
from app.schemas.chat import ChatMessageRequest, ChatResponse, HotelRecommendation
from app.services.booking_service import BookingService


class AIService:
    def __init__(self):
        genai.configure(api_key=settings.GOOGLE_GEMINI_API_KEY)
        self.model = genai.GenerativeModel("models/gemini-2.5-flash")
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
        session_id = request.session_id or str(uuid.uuid4())
        chat_session = await self._get_or_create_session(db, session_id, request.user_id)

        context = await self._extract_context(db, request.message, chat_session)

        # Intent detection (robust)
        intent = self._detect_intent(request.message)
        if intent:
            name = intent.get("name")
            details = intent.get("details", {})
            target = intent.get("target")

            if name == "show_rooms":
                text, updated_context = await self._handle_show_rooms(db, request.message, context)
                await self._update_session(db, chat_session, request.message, text, updated_context)
                return ChatResponse(response=text, session_id=session_id, recommendations=[], conversation_context=updated_context)

            if name == "hotel_details":
                text, updated_context = await self._handle_hotel_details(db, request.message, context)
                await self._update_session(db, chat_session, request.message, text, updated_context)
                return ChatResponse(response=text, session_id=session_id, recommendations=[], conversation_context=updated_context)

            if name == "current_booking":
                text, updated_context = await self._handle_booking_details(db, request.message, context, request.user_id)
                await self._update_session(db, chat_session, request.message, text, updated_context)
                return ChatResponse(response=text, session_id=session_id, recommendations=[], conversation_context=updated_context)

            if name == "book_room":
                success, payload = await self._handle_book_intent(db, chat_session, context, request.user_id, target, details)
                if success:
                    assistant_text = (
                        f"Booking confirmed: {payload.get('hotel', {}).get('name')} in "
                        f"{payload.get('hotel', {}).get('city')}. Booking id: {payload.get('booking_id')}."
                    )
                    new_context = dict(context)
                    new_context["booking"] = payload
                    await self._update_session(db, chat_session, request.message, assistant_text, new_context)
                    return ChatResponse(response=assistant_text, session_id=session_id, recommendations=[], conversation_context=new_context)
                else:
                    assistant_text = payload.get("error", "Could not create booking. Please provide missing details.")
                    await self._update_session(db, chat_session, request.message, assistant_text, context)
                    return ChatResponse(response=assistant_text, session_id=session_id, recommendations=[], conversation_context=context)

        # Otherwise attempt recommendations
        recommendations = await self._get_recommendations(db, context)
        if recommendations:
            opening = random.choice(self.openings).format(location=context.get('location', 'that area'))
            closing = random.choice(self.closings)
            rec_text = opening + "\n\n"
            for h in recommendations:
                desc = h.description or "No description available."
                rec_text += f"- {h.name} ({h.rating}★) – {h.price_range}\n  {desc}\n\n"
            rec_text += closing
            await self._update_session(db, chat_session, request.message, rec_text, context)
            return ChatResponse(response=rec_text, session_id=session_id, recommendations=recommendations, conversation_context=context)

        # No DB recommendations - ask Gemini for fallback
        fallback_raw = await self._handle_no_recommendations(chat_session, request.message, context)
        if isinstance(fallback_raw, dict):
            fallback_response = fallback_raw.get("text", "")
            context = fallback_raw.get("context", context)
        else:
            fallback_response = fallback_raw or "Sorry, I couldn't find results. Could you provide more details?"
        await self._update_session(db, chat_session, request.message, fallback_response, context)

        return ChatResponse(response=fallback_response, session_id=session_id, recommendations=[], conversation_context=context)

    async def _call_gemini(self, messages: List[Dict[str, str]]) -> str:
        try:
            prompt = self._convert_messages_to_prompt(messages)
            resp = self.model.generate(prompt=prompt, temperature=0.2, max_output_tokens=500)
            text = ""
            if resp and getattr(resp, "candidates", None):
                text = resp.candidates[0].content
            elif getattr(resp, "output", None):
                text = resp.output.get("content", "")
            return text or ""
        except Exception:
            return ""

    def _convert_messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        parts = []
        for m in messages:
            parts.append(f"{m.get('role', '').upper()}: {m.get('content', '')}")
        return "\n\n".join(parts)

    async def _get_or_create_session(self, db: AsyncSession, session_id: str, user_id: Optional[int]) -> ChatSession:
        q = select(ChatSession).where(ChatSession.session_id == session_id)
        res = await db.execute(q)
        session = res.scalars().first()
        if session:
            return session
        new = ChatSession(session_id=session_id, user_id=user_id, messages=[], context={})
        db.add(new)
        await db.commit()
        await db.refresh(new)
        return new

    async def _extract_context(self, db: AsyncSession, message: str, chat_session: ChatSession) -> Dict[str, Any]:
        ctx = dict(chat_session.context or {})
        loc = self._extract_location(message)
        if loc:
            ctx["location"] = loc
        dates = self._extract_dates(message)
        if dates:
            ctx.update(dates)
        prefs = self._extract_preferences(message)
        if prefs:
            ctx.setdefault("preferences", {}).update(prefs)
        guests = self._extract_guest_count(message)
        if guests:
            ctx.setdefault("preferences", {})["guests"] = guests
        return ctx

    def _extract_location(self, message: str) -> Optional[str]:
        if not message:
            return None
        patterns = [r"in\s+([A-Z][\w\s]+)", r"at\s+([A-Z][\w\s]+)", r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b"]
        for pat in patterns:
            m = re.search(pat, message)
            if m:
                candidate = m.group(1).strip()
                return candidate
        # fallback common city names
        known = ["New York", "Los Angeles", "Chicago", "Miami", "Seattle", "Brooklyn"]
        for city in known:
            if city.lower() in message.lower():
                return city
        return None

    def _extract_dates(self, message: str) -> Dict[str, Any]:
        d = {}
        # look for "from X to Y" or "X to Y"
        m = re.search(r"from\s+(.+?)\s+(?:to|until|through)\s+(.+?)(?:[.,;]|$)", message, flags=re.IGNORECASE)
        if not m:
            m = re.search(r"([A-Za-z0-9,\s]{3,32})\s+(?:-|to|until)\s+([A-Za-z0-9,\s]{3,32})", message, flags=re.IGNORECASE)
        if m:
            start_raw = m.group(1).strip()
            end_raw = m.group(2).strip()
            start = self._parse_date_fuzzy(start_raw)
            end = self._parse_date_fuzzy(end_raw)
            if start:
                d["check_in"] = start.isoformat()
            if end:
                d["check_out"] = end.isoformat()
            return d
        mci = re.search(r"check(?:-| )?in[:\s]+([A-Za-z0-9,\s]+)", message, flags=re.IGNORECASE)
        mco = re.search(r"check(?:-| )?out[:\s]+([A-Za-z0-9,\s]+)", message, flags=re.IGNORECASE)
        if mci:
            ci = self._parse_date_fuzzy(mci.group(1).strip())
            if ci:
                d["check_in"] = ci.isoformat()
        if mco:
            co = self._parse_date_fuzzy(mco.group(1).strip())
            if co:
                d["check_out"] = co.isoformat()
        return d

    def _extract_preferences(self, message: str) -> Dict[str, Any]:
        prefs = {}
        if not message:
            return prefs
        m = re.search(r"\$\s*?(\d{2,6})", message)
        if m:
            try:
                prefs["budget_min"] = int(m.group(1))
            except Exception:
                pass
        ml = message.lower()
        if any(w in ml for w in ['cheap', 'budget', 'affordable', 'inexpensive']):
            prefs["price_level"] = "budget"
        elif any(w in ml for w in ['luxury', 'premium', 'expensive', 'high-end']):
            prefs["price_level"] = "luxury"
        elif any(w in ml for w in ['mid-range', 'moderate']):
            prefs["price_level"] = "mid"
        if any(w in ml for w in ['western', 'indian', 'chinese', 'italian', 'mexican']):
            prefs["restaurant_pref"] = next((w for w in ['western', 'indian', 'chinese', 'italian', 'mexican'] if w in ml), None)
        amenities = []
        keys = {
            "pool": ["pool", "swimming"],
            "wifi": ["wifi", "wi-fi", "internet"],
            "parking": ["parking", "garage"],
            "gym": ["gym", "fitness"],
            "spa": ["spa", "wellness"]
        }
        for amen, kws in keys.items():
            if any(k in ml for k in kws):
                amenities.append(amen)
        if amenities:
            prefs["amenities"] = amenities
        return prefs

    def _extract_guest_count(self, message: str) -> Optional[int]:
        for pat in [r"(\d+)\s+(?:guest|people|person|adult|child|children)", r"(?:for|with)\s+(\d+)"]:
            m = re.search(pat, message, flags=re.IGNORECASE)
            if m:
                try:
                    return int(m.group(1))
                except Exception:
                    continue
        return None

    async def _get_recommendations(self, db: AsyncSession, context: Dict[str, Any]) -> List[HotelRecommendation]:
        q = select(Hotel)
        if context.get("location"):
            q = q.where(Hotel.city.ilike(f"%{context.get('location')}%"))
        if context.get("preferences", {}).get("budget_min"):
            try:
                b = float(context["preferences"]["budget_min"])
                q = q.where(Hotel.price_min <= b)
            except Exception:
                pass
        res = await db.execute(q.limit(10))
        hotels = res.scalars().all()
        out: List[HotelRecommendation] = []
        for h in hotels:
            price_range = f"${h.price_min} - ${h.price_max}"
            out.append(HotelRecommendation(id=h.id, name=h.name, city=h.city, rating=float(h.rating or 0), price_range=price_range, description=h.description, amenities=h.amenities))
        return out

    def _build_gpt_messages(self, user_messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        # simple wrapper if needed for future
        return user_messages

    async def _update_session(self, db: AsyncSession, session: ChatSession, user_message: str, assistant_message: str, context: Dict[str, Any]):
        messages = session.messages or []
        messages.append({"role": "user", "content": user_message, "timestamp": datetime.utcnow().isoformat()})
        messages.append({"role": "assistant", "content": assistant_message, "timestamp": datetime.utcnow().isoformat()})
        session.messages = messages
        session.context = context or {}
        await db.commit()
        await db.refresh(session)
        return session

    async def get_session_history(self, db: AsyncSession, session_id: str) -> Optional[ChatSession]:
        q = select(ChatSession).where(ChatSession.session_id == session_id)
        res = await db.execute(q)
        return res.scalars().first()

    def _format_gpt_response(self, text: str) -> str:
        if not text:
            return ""
        t = text.replace("\r\n", "\n")
        t = re.sub(r"\*\*(.*?)\*\*", r"\1", t)
        t = re.sub(r"^[\s]*[\*\u2022\-]+\s*", "- ", t, flags=re.MULTILINE)
        t = "\n".join(line.rstrip() for line in t.splitlines())
        t = re.sub(r"\n{3,}", "\n\n", t)
        return t.strip()

    def _parse_markdown_key_values(self, text: str) -> Dict[str, str]:
        prefs: Dict[str, str] = {}
        if not text:
            return prefs
        for line in text.splitlines():
            line = re.sub(r"^[\s\*\u2022\-]+", "", line).strip()
            m = re.match(r"^\*{0,2}\s*([^:]+)\s*:\s*(.+)$", line)
            if m:
                key = m.group(1).strip()
                val = m.group(2).strip()
                prefs[key] = val
        return prefs

    async def _handle_no_recommendations(
        self,
        chat_session: ChatSession,
        user_message: str,
        context: Dict[str, Any]
    ) -> Any:
        if context.get('location'):
            system = (
                "You are a helpful travel assistant. The user searched for hotels in "
                f"{context.get('location')}, but the internal database returned no exact matches. "
                "Provide friendly alternatives (nearby cities, search tweaks), ask one clarifying question, "
                "and emit a short preference summary in bullet form."
            )
            user_prompt = (
                f"User asked: \"{user_message}\". Context: {json.dumps(context)}. "
                "List 3 quick suggestions (nearby cities or search tweaks) and then ask one concise clarifying question. "
                "Also emit a short preference summary in bullet form (e.g. **Location:** X, **Check-in:** Y...)."
            )
        else:
            system = (
                "You are a helpful travel assistant. The user query could not be matched in the internal database. "
                "Ask a concise clarifying question to obtain a location, dates, or preferences. Offer one example search and a short preference summary if possible."
            )
            user_prompt = f"User asked: \"{user_message}\". Ask a single clarifying question and offer one example search. Include a short preference summary if possible."

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt}
        ]

        gpt_response = await self._call_gemini(messages)
        if not gpt_response or not gpt_response.strip():
            if context.get('location'):
                fallback_text = f"Sorry, I couldn't find hotels in {context.get('location')}. Would you like to try a nearby neighborhood or change dates?"
            else:
                fallback_text = "Sorry, I couldn't find any matches. Could you share a location, dates, or preferences?"
            return {"text": fallback_text, "context": context}

        cleaned = self._format_gpt_response(gpt_response)
        parsed_prefs = self._parse_markdown_key_values(gpt_response)
        new_context = dict(context) if context else {}
        if parsed_prefs:
            new_context['prompt_preferences'] = parsed_prefs
        new_context['assistant_raw'] = gpt_response
        new_context['assistant_clean'] = cleaned
        return {"text": cleaned, "context": new_context}

    def _parse_date_fuzzy(self, text: str) -> Optional[date]:
        if not text or not isinstance(text, str):
            return None
        txt = re.sub(r'(\d{1,2})(st|nd|rd|th)', r'\1', text, flags=re.IGNORECASE)
        txt = txt.replace(",", "").strip()
        fmts = ["%B %d %Y", "%b %d %Y", "%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%m/%d/%Y", "%Y/%m/%d"]
        for fmt in fmts:
            try:
                return datetime.strptime(txt, fmt).date()
            except Exception:
                continue
        try:
            return datetime.fromisoformat(text.strip()).date()
        except Exception:
            return None

    async def book_from_context(
        self,
        db: AsyncSession,
        session_id: str,
        user_id: int,
        preferred_hotel_id: Optional[int] = None
    ) -> Tuple[bool, dict]:
        session = await self.get_session_history(db, session_id)
        if not session:
            return False, {"error": "Chat session not found."}
        context = session.context or {}
        prefs = context.get("prompt_preferences") or {}
        location = prefs.get("Location") or context.get("location")
        check_in_raw = prefs.get("Check-in") or context.get("check_in") or prefs.get("Checkin") or prefs.get("Check in")
        check_out_raw = prefs.get("Check-out") or context.get("check_out") or prefs.get("Checkout") or prefs.get("Check out")
        guests_raw = prefs.get("Guests") or context.get("preferences", {}).get("guests") or context.get("guests")
        guests = 1
        if isinstance(guests_raw, int):
            guests = guests_raw
        elif isinstance(guests_raw, str):
            m = re.search(r"(\d+)", guests_raw)
            if m:
                guests = int(m.group(1))
        check_in = self._parse_date_fuzzy(str(check_in_raw)) if check_in_raw else None
        check_out = self._parse_date_fuzzy(str(check_out_raw)) if check_out_raw else None
        if not location or not check_in or not check_out:
            return False, {"error": "Missing booking details. Need location, check-in, and check-out dates in the chat context."}
        if preferred_hotel_id:
            q = select(Hotel).where(Hotel.id == preferred_hotel_id)
        else:
            q = select(Hotel).where(Hotel.city.ilike(f"%{location}%"))
            budget_min = context.get("preferences", {}).get("budget_min") or prefs.get("Budget") or prefs.get("Budget_min")
            if isinstance(budget_min, (int, float, str)):
                try:
                    bmin = float(budget_min)
                    q = q.where(Hotel.price_min <= bmin)
                except Exception:
                    pass
        res = await db.execute(q)
        hotel = res.scalars().first()
        if not hotel:
            return False, {"error": f"No hotel found for location '{location}'."}
        rq = select(Room).where(and_(Room.hotel_id == hotel.id, Room.available == True))
        rres = await db.execute(rq)
        room = rres.scalars().first()
        if not room:
            return False, {"error": "No available rooms found for the selected hotel."}
        from app.schemas.booking import BookingCreate
        booking_payload = BookingCreate(
            user_id=user_id,
            hotel_id=hotel.id,
            room_id=room.id,
            check_in=check_in,
            check_out=check_out,
            guests=guests,
            status="pending"
        )
        try:
            booking = await BookingService.create_booking(db, booking_payload)
        except Exception as e:
            return False, {"error": f"Booking failed: {str(e)}"}
        assistant_msg = (
            f"Booking created: {hotel.name} in {hotel.city}, room {room.room_type}. "
            f"Check-in: {booking_payload.check_in.isoformat()}, Check-out: {booking_payload.check_out.isoformat()}, Guests: {guests}."
        )
        await self._update_session(db, session, "Book hotel (from chat)", assistant_msg, {**context, "booking_id": booking.id})
        return True, {
            "booking_id": booking.id,
            "hotel": {"id": hotel.id, "name": hotel.name, "city": hotel.city},
            "room": {"id": room.id, "room_type": room.room_type, "price": str(room.price)},
            "check_in": booking_payload.check_in.isoformat(),
            "check_out": booking_payload.check_out.isoformat(),
            "guests": guests,
            "status": booking.status
        }

    def _detect_intent(self, message: str) -> Optional[Dict[str, Any]]:
        ml = message.lower()
        details = self._extract_booking_details_from_text(message)
        booking_keywords = [r"\bbook\b", r"\breserve\b", r"\breservation\b", r"\bconfirm\b", r"\bhold\b"]
        if any(re.search(k, ml) for k in booking_keywords):
            if re.search(r"\bcancel\b|\bdelete\b", ml):
                return {"name": "cancel_booking", "target": None, "details": details}
            if re.search(r"\bchange\b|\bmodify\b|\bupdate\b|\breschedule\b", ml):
                return {"name": "modify_booking", "target": None, "details": details}
            target = None
            quoted = re.search(r"\"([^\"]+)\"", message)
            if quoted:
                target = quoted.group(1).strip()
            else:
                m = re.search(r"\bat\s+(?:the\s+)?([A-Z0-9][\w\s&\.'\-]+)", message)
                if m:
                    target = m.group(1).strip()
            return {"name": "book_room", "target": target, "details": details}
        if re.search(r"\b(?:rooms available|what rooms|available rooms|show rooms|room types|room options)\b", ml):
            target = details.get("hotel") or None
            return {"name": "show_rooms", "target": target, "details": details}
        if re.search(r"\b(?:details about|tell me about|hotel details|amenit(?:y|ies)|rating|address|phone)\b", ml):
            target = details.get("hotel") or None
            return {"name": "hotel_details", "target": target, "details": details}
        if re.search(r"\b(?:my booking|my bookings|current booking|reservations|show my reservations|what bookings)\b", ml):
            return {"name": "current_booking", "target": None, "details": details}
        return None

    def _extract_booking_details_from_text(self, text: str) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        if not text or not isinstance(text, str):
            return out
        quoted = re.search(r"\"([^\"]+)\"", text)
        if quoted:
            out["hotel"] = quoted.group(1).strip()
        else:
            m_at = re.search(r"\bat\s+(?:the\s+)?([A-Z0-9][\w\s&\.'\-]+)", text)
            if m_at:
                out["hotel"] = m_at.group(1).strip()
            else:
                m_in = re.search(r"\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", text)
                if m_in:
                    out["location"] = m_in.group(1).strip()
        room_keywords = ["single", "double", "suite", "deluxe", "standard", "king", "queen", "family", "studio", "executive"]
        for kw in room_keywords:
            if re.search(rf"\b{kw}\b", text, flags=re.IGNORECASE):
                out.setdefault("room_type", kw)
                break
        m_budget = re.search(r"\$\s*([0-9]{2,7})", text)
        if m_budget:
            try:
                out["budget_min"] = int(m_budget.group(1))
            except Exception:
                pass
        total_guests = 0
        m_guests = re.search(r"for\s+((?:\d+\s*(?:adults?|children?|kids?|people|persons|guests?)(?:\s*(?:and|,)\s*)?)+)", text, flags=re.IGNORECASE)
        if m_guests:
            parts = re.findall(r"(\d+)\s*(?:adults?|children?|kids?|people|persons|guests?)", m_guests.group(1), flags=re.IGNORECASE)
            for p in parts:
                try:
                    total_guests += int(p)
                except Exception:
                    pass
        else:
            m_for = re.search(r"\bfor\s+(\d+)\b", text)
            if m_for:
                total_guests = int(m_for.group(1))
        if total_guests > 0:
            out["guests"] = total_guests
        m_range = re.search(r"\bfrom\s+(.+?)\s+(?:to|until|through)\s+(.+?)(?:\b|$)", text, flags=re.IGNORECASE)
        if not m_range:
            m_range = re.search(r"((?:[A-Za-z]{3,9}\s*\d{1,2}(?:st|nd|rd|th)?(?:,?\s*\d{4})?))\s*(?:-|to|until|through)\s*((?:[A-Za-z]{3,9}\s*\d{1,2}(?:st|nd|rd|th)?(?:,?\s*\d{4})?))", text, flags=re.IGNORECASE)
        if m_range:
            raw_start = m_range.group(1).strip().strip(",")
            raw_end = m_range.group(2).strip().strip(",")
            start = self._parse_date_fuzzy(raw_start)
            end = self._parse_date_fuzzy(raw_end)
            if start:
                out["check_in"] = start.isoformat()
            if end:
                out["check_out"] = end.isoformat()
        else:
            m_ci = re.search(r"check(?:-| )?in[:\s]+([A-Za-z0-9,\s]+)", text, flags=re.IGNORECASE)
            m_co = re.search(r"check(?:-| )?out[:\s]+([A-Za-z0-9,\s]+)", text, flags=re.IGNORECASE)
            if m_ci:
                ci = self._parse_date_fuzzy(m_ci.group(1).strip())
                if ci:
                    out["check_in"] = ci.isoformat()
            if m_co:
                co = self._parse_date_fuzzy(m_co.group(1).strip())
                if co:
                    out["check_out"] = co.isoformat()
        return out

    async def _handle_show_rooms(self, db: AsyncSession, message: str, context: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        target = None
        quoted = re.search(r"\"([^\"]+)\"", message)
        m = re.search(r"rooms? (?:at|in)\s+([A-Z0-9][\w\s&'\-]+)", message)
        if quoted:
            target = quoted.group(1).strip()
        elif m:
            target = m.group(1).strip()
        elif context.get("location"):
            target = context.get("location")
        if not target:
            return ("Which hotel or city would you like to see room types for?", context)
        q = select(Hotel).where(or_(Hotel.name.ilike(f"%{target}%"), Hotel.city.ilike(f"%{target}%")))
        res = await db.execute(q)
        hotels = res.scalars().all()
        if not hotels:
            return (f"Sorry, I couldn't find any hotels matching '{target}'. Try a different name or city.", context)
        lines = []
        new_ctx = dict(context)
        hotels_info = []
        for h in hotels:
            rq = select(Room).where(and_(Room.hotel_id == h.id, Room.available == True))
            rres = await db.execute(rq)
            rooms = rres.scalars().all()
            hotels_info.append({"hotel": {"id": h.id, "name": h.name, "city": h.city}, "rooms": [{"id": r.id, "room_type": r.room_type, "price": str(r.price), "available": r.available} for r in rooms]})
            lines.append(f"{h.name} — {h.city} ({len(rooms)} available rooms)")
            for r in rooms:
                lines.append(f"  - {r.room_type}: ${r.price} — {'Available' if r.available else 'Unavailable'}")
            lines.append("")
        new_ctx["last_room_list"] = hotels_info
        text = "Rooms found:\n\n" + "\n".join(lines).strip()
        return (text, new_ctx)

    async def _handle_hotel_details(self, db: AsyncSession, message: str, context: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        quoted = re.search(r"\"([^\"]+)\"", message)
        m = re.search(r"(?:about|details about|details for|of)\s+([A-Z0-9][\w\s&'\-]+)", message)
        target = quoted.group(1).strip() if quoted else (m.group(1).strip() if m else context.get("location"))
        if not target:
            return ("Which hotel would you like details for? Please provide hotel name or city.", context)
        q = select(Hotel).where(or_(Hotel.name.ilike(f"%{target}%"), Hotel.city.ilike(f"%{target}%")))
        res = await db.execute(q)
        hotels = res.scalars().all()
        if not hotels:
            return (f"Could not find hotel matching '{target}'. Try a different name or a nearby city.", context)
        pieces = []
        new_ctx = dict(context)
        hotel_summaries = []
        for h in hotels:
            amenities = ", ".join(h.amenities or []) if h.amenities else "None listed"
            pieces.append(f"{h.name} — {h.city}\nRating: {float(h.rating or 0):.1f}★\nPrice range: ${h.price_min} - ${h.price_max}\nAmenities: {amenities}\n{h.description or ''}\n")
            hotel_summaries.append({"id": h.id, "name": h.name, "city": h.city, "rating": float(h.rating or 0)})
        new_ctx["last_hotel_details"] = hotel_summaries
        text = "Hotel details:\n\n" + "\n".join(pieces).strip()
        return (text, new_ctx)

    async def _handle_booking_details(self, db: AsyncSession, message: str, context: Dict[str, Any], user_id: Optional[int]) -> Tuple[str, Dict[str, Any]]:
        if not user_id:
            return ("I don't have your account info. Please provide your user id or sign in to see your bookings.", context)
        bookings = await BookingService.get_booking_by_user_id(db, user_id)
        if not bookings:
            return ("No bookings found for your account.", context)
        lines = []
        for b in bookings:
            lines.append(f"Booking id: {b['id']} — {b['name']} in {b['city']}\nRoom: {b['room_type']} — ${b['price']}\nCheck-in: {b['check_in']}, Check-out: {b['check_out']}\nGuests: {b['guests']}\nStatus: {b['status']}\n")
        new_ctx = dict(context)
        new_ctx["last_bookings"] = bookings
        text = "Your bookings:\n\n" + "\n".join(lines).strip()
        return (text, new_ctx)

    async def _handle_book_intent(self, db: AsyncSession, chat_session: ChatSession, context: Dict[str, Any], user_id: Optional[int], target: Optional[str], details: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        if not user_id:
            return False, {"error": "You must be signed in (provide user_id) to make a booking."}
        working = dict(context or {})
        for k, v in (details or {}).items():
            if v is not None:
                working[k] = v
        if target:
            working["hotel_target"] = target
        if not (working.get("check_in") and working.get("check_out")):
            return False, {"error": "Missing dates. Please provide check-in and check-out dates (e.g. Oct 22 to Oct 28)."}
        parsed_prefs = working.get("prompt_preferences", {})
        if working.get("hotel"):
            parsed_prefs.setdefault("Location", working.get("hotel"))
        if working.get("check_in"):
            parsed_prefs.setdefault("Check-in", working.get("check_in"))
        if working.get("check_out"):
            parsed_prefs.setdefault("Check-out", working.get("check_out"))
        if working.get("guests"):
            parsed_prefs.setdefault("Guests", str(working.get("guests")))
        if working.get("budget_min"):
            parsed_prefs.setdefault("Budget", str(working.get("budget_min")))
        await self._update_session(db, chat_session, "User requested booking (parsed)", "(assistant will attempt booking)", {**context, "prompt_preferences": parsed_prefs})
        return await self.book_from_context(db, chat_session.session_id, user_id, preferred_hotel_id=None)
