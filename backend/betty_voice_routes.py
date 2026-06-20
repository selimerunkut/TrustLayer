"""Betty voice API: LangGraph broker + ElevenLabs TTS for the Streamlit voice embed."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_MAX_SESSIONS = 80


class BettyVoiceChatRequest(BaseModel):
    thread_id: str = Field(min_length=8, max_length=128)
    message: str = Field(min_length=1, max_length=16000)
    crm_customer_id: str = Field(default="vasiliy", max_length=64)


class BettyTtsRequest(BaseModel):
    text: str = Field(min_length=1, max_length=16000)


def _prune_voice_sessions(app: FastAPI) -> None:
    store: dict[str, tuple[Any, Any]] = app.state.voice_broker_sessions  # type: ignore[attr-defined]
    while len(store) > _MAX_SESSIONS:
        store.pop(next(iter(store)))


def _get_or_create_session(app: FastAPI, thread_id: str) -> tuple[Any, Any]:
    if not hasattr(app.state, "voice_broker_sessions"):
        app.state.voice_broker_sessions = {}
    store: dict[str, tuple[Any, Any]] = app.state.voice_broker_sessions
    if thread_id not in store:
        from coverpilot_conversation.agent import build_broker_agent

        agent, backend = build_broker_agent()
        store[thread_id] = (agent, backend)
        _prune_voice_sessions(app)
    return store[thread_id]


def register_betty_voice_routes(app: FastAPI) -> None:
    router = APIRouter(tags=["betty-voice"])

    @router.post("/api/betty/voice-chat")
    def betty_voice_chat(request: Request, body: BettyVoiceChatRequest) -> dict[str, str]:
        if not os.getenv("OPENAI_API_KEY", "").strip():
            raise HTTPException(status_code=503, detail="OPENAI_API_KEY is not configured on the API server.")
        agent, backend = _get_or_create_session(request.app, body.thread_id)
        backend.session_customer_id = (body.crm_customer_id or "vasiliy").strip().lower()

        from coverpilot_conversation.customer_directory import (
            session_crm_context_block,
            user_message_suggests_travel_planning,
        )
        from coverpilot_conversation.message_extract import extract_last_ai_text

        payload = body.message.strip()
        if user_message_suggests_travel_planning(payload):
            crm = session_crm_context_block(session_default_customer_id=backend.session_customer_id)
            if crm:
                payload = f"{crm}\n\n---\nTraveler message:\n{payload}"

        config = {
            "configurable": {"thread_id": body.thread_id},
            "recursion_limit": int(os.getenv("COVERPILOT_RECURSION_LIMIT", "25")),
        }
        try:
            result = agent.invoke({"messages": [{"role": "user", "content": payload}]}, config=config)
        except Exception as e:
            logger.exception("Betty voice-chat invoke failed")
            raise HTTPException(status_code=500, detail=str(e)) from e

        reply = extract_last_ai_text(result)
        return {"reply": reply, "thread_id": body.thread_id}

    @router.post("/api/betty/tts")
    def betty_tts(body: BettyTtsRequest) -> Response:
        try:
            from backend.services.elevenlabs_voice import elevenlabs_configured, synthesize_speech_mp3
        except ImportError as e:
            raise HTTPException(status_code=500, detail="ElevenLabs module not available.") from e
        if not elevenlabs_configured():
            raise HTTPException(status_code=503, detail="ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID not set.")
        try:
            mp3 = synthesize_speech_mp3(body.text)
        except Exception as e:
            logger.exception("TTS failed")
            raise HTTPException(status_code=500, detail=str(e)) from e
        return Response(content=mp3, media_type="audio/mpeg")

    app.include_router(router)
