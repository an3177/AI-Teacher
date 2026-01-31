
from pathlib import Path
import logging
from typing import List
import time
import uuid
import asyncio
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from fastapi import Depends, FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from groq import AsyncGroq
from pydantic_ai import Agent
from sqlalchemy.orm import Session

from app.lifespan import app_lifespan as lifespan
from app.llm import Dependencies
from app.settings import get_settings
from app.stt import transcribe_audio_data
from app.database import get_session_maker
from app.models import Session as DBSession, Conversation

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Friend - Voice Chat", lifespan=lifespan)

# Thread pool for offloading blocking DB writes
db_thread_pool = ThreadPoolExecutor(max_workers=4)

app.mount("/chatroom", StaticFiles(directory="chatroom"), name="chatroom")
app.mount("/background", StaticFiles(directory="background"), name="background")
app.mount("/images", StaticFiles(directory="images"), name="images")


async def get_agent_dependencies(websocket: WebSocket) -> Dependencies:
    return Dependencies(
        settings=get_settings(),
        session=websocket.app.state.aiohttp_session,
    )


async def get_groq_client(websocket: WebSocket) -> AsyncGroq:
    return websocket.app.state.groq_client


async def get_agent(websocket: WebSocket) -> Agent:
    return websocket.app.state.groq_agent


def _save_conversation_sync(SessionLocal, session_id, user_transcript, ai_response, audio_duration, processing_time):
    """Blocking DB write — runs in thread pool so it doesn't block the event loop."""
    db = SessionLocal()
    try:
        conversation = Conversation(
            session_id=session_id,
            user_transcript=user_transcript,
            ai_response=ai_response,
            audio_duration=audio_duration,
            processing_time=processing_time
        )
        db.add(conversation)
        db.commit()
        logger.info(f"Saved conversation (session_id={session_id}, processing_time={processing_time:.2f}s)")
    except Exception as e:
        logger.error(f"Failed to save conversation: {e}")
        db.rollback()
    finally:
        db.close()


@app.websocket("/voice_chat")
async def voice_chat(
    websocket: WebSocket,
    groq_client: AsyncGroq = Depends(get_groq_client),
    agent: Agent[Dependencies] = Depends(get_agent),
    agent_deps: Dependencies = Depends(get_agent_dependencies),
):
    await websocket.accept()
    logger.info("WebSocket connection accepted")

    settings = get_settings()
    SessionLocal = get_session_maker(settings)

    # Create session
    db = SessionLocal()
    db_session = None
    try:
        session_token = str(uuid.uuid4())
        db_session = DBSession(
            session_token=session_token,
            is_active=True
        )
        db.add(db_session)
        db.commit()
        db.refresh(db_session)
        session_id = db_session.id  # Cache the ID so we don't need db_session later
        logger.info(f"Created database session: {session_token} (ID: {session_id})")
    except Exception as e:
        logger.error(f"Failed to create database session: {e}")
        db.rollback()
        session_id = None
    finally:
        db.close()  # Close immediately — we don't hold this connection open

    try:
        async for audio_data in websocket.iter_bytes():
            logger.info(f"Received audio: {len(audio_data)} bytes")

            # Skip anything too small to be real speech
            if len(audio_data) < 8000:
                logger.info(f"Skipping small chunk ({len(audio_data)} bytes)")
                continue

            start_time = time.time()

            try:
                # Transcribe
                logger.info(f"Transcribing {len(audio_data)} bytes...")
                transcription = await transcribe_audio_data(
                    audio_data=audio_data,
                    api_client=groq_client
                )

                if not transcription or not transcription.strip():
                    logger.warning("Empty transcription, skipping")
                    continue

                logger.info(f"User said: '{transcription}'")

                # Send user transcript to frontend immediately
                await websocket.send_json({
                    "type": "user_transcript",
                    "text": transcription
                })

                # Get AI response via streaming
                logger.info("Generating AI response...")
                ai_response = ""

                async with agent.run_stream(
                    user_prompt=transcription,
                    deps=agent_deps
                ) as result:
                    async for delta in result.stream_text(delta=True):
                        ai_response += delta

                # Send AI response to frontend
                await websocket.send_json({
                    "type": "ai_transcript",
                    "text": ai_response
                })

                logger.info(f"AI said: '{ai_response}'")

                processing_time = time.time() - start_time
                # Estimate audio duration from webm size (rough: ~16kbps opus)
                audio_duration = len(audio_data) / 16000

                # Fire-and-forget DB write in thread pool — doesn't block the loop
                if session_id:
                    asyncio.get_event_loop().run_in_executor(
                        db_thread_pool,
                        _save_conversation_sync,
                        SessionLocal,
                        session_id,
                        transcription,
                        ai_response,
                        audio_duration,
                        processing_time
                    )

            except Exception as e:
                logger.error(f"Error processing audio: {type(e).__name__}: {e}")
                continue

    except Exception as e:
        logger.error(f"WebSocket error: {type(e).__name__}: {e}")
    finally:
        # End session
        if session_id:
            db = SessionLocal()
            try:
                session = db.query(DBSession).filter(DBSession.id == session_id).first()
                if session:
                    session.is_active = False
                    session.ended_at = datetime.utcnow()
                    db.commit()
                    logger.info(f"Session {session_token} ended")
            except Exception as e:
                logger.error(f"Error closing session: {e}")
                db.rollback()
            finally:
                db.close()

        logger.info("WebSocket connection closed")


@app.get("/")
async def get_welcome():
    with Path("background/welcome.html").open("r", encoding="utf-8") as file:
        return HTMLResponse(file.read())


@app.get("/chat")
async def get_chat():
    with Path("chatroom/index.html").open("r", encoding="utf-8") as file:
        return HTMLResponse(file.read())


@app.get("/api/sessions/{session_token}")
async def get_session_history(session_token: str):
    """Get conversation history for a specific session."""
    settings = get_settings()
    SessionLocal = get_session_maker(settings)
    db = SessionLocal()

    try:
        session = db.query(DBSession).filter(DBSession.session_token == session_token).first()
        if not session:
            return {"error": "Session not found"}

        conversations = db.query(Conversation).filter(Conversation.session_id == session.id).all()

        return {
            "session_token": session.session_token,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
            "is_active": session.is_active,
            "conversation_count": len(conversations),
            "conversations": [
                {
                    "user_transcript": conv.user_transcript,
                    "ai_response": conv.ai_response,
                    "created_at": conv.created_at.isoformat() if conv.created_at else None,
                    "processing_time": conv.processing_time
                }
                for conv in conversations
            ]
        }
    finally:
        db.close()


@app.get("/api/sessions")
async def get_all_sessions(limit: int = 50):
    """Get all practice sessions with conversation counts."""
    settings = get_settings()
    SessionLocal = get_session_maker(settings)
    db = SessionLocal()

    try:
        sessions = db.query(DBSession).order_by(DBSession.started_at.desc()).limit(limit).all()

        result = []
        for session in sessions:
            conv_count = db.query(Conversation).filter(Conversation.session_id == session.id).count()
            result.append({
                "session_token": session.session_token,
                "started_at": session.started_at.isoformat() if session.started_at else None,
                "ended_at": session.ended_at.isoformat() if session.ended_at else None,
                "is_active": session.is_active,
                "conversation_count": conv_count
            })

        return {
            "total_sessions": len(result),
            "sessions": result
        }
    finally:
        db.close()


@app.get("/health")
async def health_check():
    """Health check endpoint to verify app and database are running."""
    from sqlalchemy import text

    settings = get_settings()
    SessionLocal = get_session_maker(settings)
    db = SessionLocal()

    try:
        db.execute(text("SELECT 1"))

        session_count = db.query(DBSession).count()
        conversation_count = db.query(Conversation).count()

        return {
            "status": "healthy",
            "database": "connected",
            "total_sessions": session_count,
            "total_conversations": conversation_count
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }
    finally:
        db.close()