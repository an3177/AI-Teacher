from groq import AsyncGroq
import logging
import tempfile
import os

logger = logging.getLogger(__name__)


async def transcribe_audio_data(
    audio_data: bytes,
    api_client: AsyncGroq,
    model_name: str = "whisper-large-v3-turbo",
    temperature: float = 0.0,
    language: str = "en"
) -> str:
    # Transcribe audio data using Groq's Whisper model.
    logger.info(f"Attempting to transcribe {len(audio_data)} bytes of audio")
    
    temp_file_path = None
    try:
        # Create temp file with .webm extension
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.webm', delete=False) as temp_file:
            temp_file.write(audio_data)
            temp_file_path = temp_file.name
        
        logger.info(f"Saved audio to temp file: {temp_file_path}")
        
        # Open and send the file
        with open(temp_file_path, 'rb') as audio_file:
            logger.info("Calling Groq transcription API...")
            response = await api_client.audio.transcriptions.create(
                model=model_name,
                file=audio_file,
                temperature=temperature,
                language=language,
                response_format="text" #get plain text response
            )
            
            # Extract transcription text
            text = response.strip() if isinstance(response, str) else response.text.strip()
            logger.info(f"Transcription successful: '{text}'")
            return text
            
    except Exception as e:
        #log transcription errors
        logger.error(f"Transcription error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return ""
    finally:
        # Clean up temp file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                logger.info(f"Cleaned up temp file: {temp_file_path}")
            except Exception as e:
                #log warning if temp file deletion fails
                logger.warning(f"Could not delete temp file: {e}")