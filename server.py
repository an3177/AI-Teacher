# server.py
from pathlib import Path
import logging
from typing import List
import time
import uuid
from datetime import datetime

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

# Add logging with timestamps and formatting
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app with lifespan
app = FastAPI(title="AI Friend - Voice Chat", lifespan=lifespan)

# Mount static files from chatroom, background, and images directories
app.mount("/chatroom", StaticFiles(directory="chatroom"), name="chatroom")
app.mount("/background", StaticFiles(directory="background"), name="background")
app.mount("/images", StaticFiles(directory="images"), name="images")


# FastAPI dependency to get agent dependencies
async def get_agent_dependencies(websocket: WebSocket) -> Dependencies:
    return Dependencies(
        settings=get_settings(),
        session=websocket.app.state.aiohttp_session,
    )


async def get_groq_client(websocket: WebSocket) -> AsyncGroq:
    return websocket.app.state.groq_client


async def get_agent(websocket: WebSocket) -> Agent:
    return websocket.app.state.groq_agent


# WebSocket endpoint for voice chat
@app.websocket("/voice_chat")
async def voice_chat(
    websocket: WebSocket,
    groq_client: AsyncGroq = Depends(get_groq_client),
    agent: Agent[Dependencies] = Depends(get_agent),
    agent_deps: Dependencies = Depends(get_agent_dependencies),
):
    await websocket.accept()
    logger.info("WebSocket connection accepted")

    # Get session maker
    settings = get_settings()
    SessionLocal = get_session_maker(settings)
    
    # Create database session
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
        logger.info(f"Created database session: {session_token} (ID: {db_session.id})")
    except Exception as e:
        logger.error(f" Failed to create database session: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()

    # Buffer to accumulate audio chunks
    audio_buffer: List[bytes] = []
    min_audio_size = 8000  # Minimum bytes before transcription
    max_buffer_size = 500000  # Max bytes to buffer before processing
    
    try:
        async for incoming_audio_bytes in websocket.iter_bytes():
            logger.info(f"Received audio chunk: {len(incoming_audio_bytes)} bytes")
            
            # Add to buffer
            audio_buffer.append(incoming_audio_bytes)
            total_buffered = sum(len(chunk) for chunk in audio_buffer)
            logger.info(f"Buffer size: {total_buffered} bytes")
            
            # Process when we either have minimum audio or reached max buffer size
            should_process = (total_buffered >= min_audio_size and incoming_audio_bytes == b'') or total_buffered >= max_buffer_size
            
            if not should_process and total_buffered < max_buffer_size:
                logger.info(f"Buffering audio ({total_buffered} bytes)")
                continue
            
            # Combine all buffered audio
            combined_audio = b''.join(audio_buffer)
            audio_buffer.clear()
            logger.info(f" User finished speaking - processing {len(combined_audio)} bytes")
            
            # Track processing time
            start_time = time.time()
            
            try:
                # Transcribe user's speech
                logger.info(f" Transcribing {len(combined_audio)} bytes...")
                transcription = await transcribe_audio_data(
                    audio_data=combined_audio,
                    api_client=groq_client
                )
                
                logger.info(f" User said: '{transcription}'")
                
                # Skip if transcription is empty
                if not transcription or len(transcription.strip()) == 0:
                    logger.warning("Empty transcription")
                    continue

                # Send transcription to frontend
                await websocket.send_json({
                    "type": "user_transcript",
                    "text": transcription
                })

                # Generate AI's response
                logger.info("Generating AI response")
                ai_response = ""
                
                async with agent.run_stream(
                    user_prompt=transcription,
                    deps=agent_deps
                ) as result:
                    # Stream text response
                    async for message in result.stream_text(delta=True):
                        ai_response += message
                        logger.info(f" AI text delta: '{message}'")
                
                # Send complete AI response text to frontend
                await websocket.send_json({
                    "type": "ai_transcript",
                    "text": ai_response
                })
                
                logger.info(f" AI said: '{ai_response}'")
                
                # Calculate processing time
                processing_time = time.time() - start_time
                
                # Save conversation to database
                if db_session:
                    try:
                        conversation = Conversation(
                            session_id=db_session.id,
                            user_transcript=transcription,
                            ai_response=ai_response,
                            processing_time=processing_time
                        )
                        db.add(conversation)
                        db.commit()
                        logger.info(f"Saved conversation to database (session_id={db_session.id}, processing_time={processing_time:.2f}s)")
                    except Exception as db_error:
                        logger.error(f"Failed to save conversation to database: {db_error}")
                        import traceback
                        traceback.print_exc()
                        db.rollback()
                else:
                    logger.warning("No database session, conversation not saved")
            
            # Log error info
            except Exception as e:
                logger.error(f" Error processing audio: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                audio_buffer.clear()
                continue
                
    except Exception as e:
        # Log WebSocket errors
        logger.error(f" WebSocket error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Mark session as inactive and set end time
        if db_session:
            try:
                db_session.is_active = False
                db_session.ended_at = datetime.utcnow()
                db.commit()
                logger.info(f" Session {db_session.session_token} ended (ID: {db_session.id})")
            except Exception as e:
                logger.error(f" Error closing database session: {e}")
                db.rollback()
        
        db.close()
        logger.info("🔌 WebSocket connection closed")


# HTTP endpoint for welcome page
@app.get("/")
async def get_welcome():
    with Path("background/welcome.html").open("r", encoding="utf-8") as file:
        return HTMLResponse(file.read())


# HTTP endpoint for chat page
@app.get("/chat")
async def get_chat():
    with Path("chatroom/index.html").open("r", encoding="utf-8") as file:
        return HTMLResponse(file.read())


# API endpoint to get session history
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


# API endpoint to get all sessions
@app.get("/api/sessions")
async def get_all_sessions(limit: int = 50):
    #Get all practice sessions with conversation counts.
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


# Health check endpoint
@app.get("/health")
async def health_check():
    #Health check endpoint to verify app and database are running
    from sqlalchemy import text
    
    settings = get_settings()
    SessionLocal = get_session_maker(settings)
    db = SessionLocal()
    
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        
        # Count sessions and conversations
        session_count = db.query(DBSession).count()
        conversation_count = db.query(Conversation).count()
        
        return {
            "status": "healthy",
            "database": "connected",
            "total_sessions": session_count,
            "total_conversations": conversation_count
        }
    except Exception as e:
        logger.error(f" Health check failed: {e}")
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }
    finally:
        db.close()