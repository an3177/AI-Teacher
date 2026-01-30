# server.py
from pathlib import Path
import logging
from typing import List

from fastapi import Depends, FastAPI, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from groq import AsyncGroq
from pydantic_ai import Agent

from app.lifespan import app_lifespan as lifespan
from app.llm import Dependencies
from app.settings import get_settings
from app.stt import transcribe_audio_data

#Add logging with timestamps and formatting
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

#Initialize FastAPI app with lifespan
app = FastAPI(title="AI Friend - Voice Chat", lifespan=lifespan)

# Mount static files from chatroom, background, and images directories
app.mount("/chatroom", StaticFiles(directory="chatroom"), name="chatroom")
app.mount("/background", StaticFiles(directory="background"), name="background")
app.mount("/images", StaticFiles(directory="images"), name="images")

#FastAPI dependency to get agent dependencies
async def get_agent_dependencies(websocket: WebSocket) -> Dependencies:
    return Dependencies(
        settings=get_settings(),
        session=websocket.app.state.aiohttp_session,
    )

async def get_groq_client(websocket: WebSocket) -> AsyncGroq:
    return websocket.app.state.groq_client


async def get_agent(websocket: WebSocket) -> Agent:
    return websocket.app.state.groq_agent


#websocket endpoint for voice chat
@app.websocket("/voice_chat")
async def voice_chat(
    websocket: WebSocket,
    groq_client: AsyncGroq = Depends(get_groq_client),
    agent: Agent[Dependencies] = Depends(get_agent),
    agent_deps: Dependencies = Depends(get_agent_dependencies),
):
    await websocket.accept()
    logger.info("WebSocket connection accepted")

    # Buffer to accumulate audio chunks
    audio_buffer: List[bytes] = []
    min_audio_size = 8000  # Minimum bytes before transcription
    max_buffer_size = 500000  # Max bytes to buffer before processing
    
    try:
        async for incoming_audio_bytes in websocket.iter_bytes():
            logger.info(f" Received audio chunk: {len(incoming_audio_bytes)} bytes")
            
            # Add to buffer
            audio_buffer.append(incoming_audio_bytes)
            total_buffered = sum(len(chunk) for chunk in audio_buffer)
            logger.info(f" Buffer size: {total_buffered} bytes")
            
            # Process when we either have minimum audio or reached max buffer size
            should_process = (total_buffered >= min_audio_size and incoming_audio_bytes == b'') or total_buffered >= max_buffer_size
            
            if not should_process and total_buffered < max_buffer_size:
                logger.info(f"Buffering audio... ({total_buffered} bytes)")
                continue
            
            # Combine all buffered audio
            combined_audio = b''.join(audio_buffer)
            audio_buffer.clear()
            logger.info(f"🎙️  User finished speaking - processing {len(combined_audio)} bytes")
            
            try:
                # Transcribe user's speech
                logger.info(f" Transcribing {len(combined_audio)} bytes...")
                transcription = await transcribe_audio_data(
                    audio_data=combined_audio,
                    api_client=groq_client
                )
                
                logger.info(f"User said: '{transcription}'")
                
                #skip if transcription is empty
                if not transcription or len(transcription.strip()) == 0:
                    logger.warning(" Empty transcription, skipping...")
                    continue

                # Send transcription to frontend
                await websocket.send_json({
                    "type": "user_transcript",
                    "text": transcription
                })

                #Generate AI's response
                logger.info(" Generating AI response...")
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
                
                logger.info(f"AI said: '{ai_response}'")
            
            #log error info
            except Exception as e:
                logger.error(f"Error processing audio: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
                audio_buffer.clear()
                continue
                
    except Exception as e:
        #log websocket errors
        logger.error(f" WebSocket error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        logger.info(" WebSocket connection closed")

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