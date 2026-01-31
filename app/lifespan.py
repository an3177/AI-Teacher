# app/lifespan.py
from contextlib import asynccontextmanager
from typing import AsyncIterator, TypedDict
import logging
import asyncio

import aiohttp
from fastapi import FastAPI
from groq import AsyncGroq
from openai import AsyncOpenAI
from pydantic_ai import Agent
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.providers.groq import GroqProvider

from app.llm import Dependencies, create_groq_agent
from app.settings import Settings, get_settings
from app.database import init_database  # Import database initialization

logger = logging.getLogger(__name__)


# Create aiohttp ClientSession
def create_aiohttp_session() -> aiohttp.ClientSession:
    return aiohttp.ClientSession()


# Create Groq client
def create_groq_client(settings: Settings) -> AsyncGroq:
    return AsyncGroq(api_key=settings.groq_api_key)


# Create Groq model
def create_groq_model(settings: Settings) -> GroqModel:
    # Create provider with API key
    provider = GroqProvider(api_key=settings.groq_api_key)
    return GroqModel("llama-3.3-70b-versatile", provider=provider)


# Define application state type
class State(TypedDict):
    aiohttp_session: aiohttp.ClientSession
    groq_client: AsyncGroq
    openai_client: AsyncOpenAI
    groq_agent: Agent[Dependencies]


@asynccontextmanager
async def app_lifespan(app: FastAPI) -> AsyncIterator[State]:
    """FastAPI lifespan manager - handles startup and shutdown"""
    logger.info(" Starting app")
    settings = get_settings()
    
    # Initialize variables
    aiohttp_session = None
    groq_client = None
    groq_agent = None
    
    try:
        # 1. Initialize database FIRST (critical for data persistence)
        logger.info("Initializing database")
        try:
            # Run migrations using Alembic
            await asyncio.to_thread(init_database, settings)
            logger.info("Database initialized successfully")
        except Exception as db_error:
            logger.error(f"Database initialization failed: {db_error}")
            import traceback
            traceback.print_exc()
            # Continue anyway - app can work without DB
        
        # 2. Initialize aiohttp session
        logger.info(" Creating aiohttp session")
        aiohttp_session = create_aiohttp_session()
        logger.info("Aiohttp session created")
        
        # 3. Initialize OpenAI client
        logger.info("OpenAI client created")
        
        # 4. Initialize Groq client
        logger.info("Creating Groq client")
        groq_client = create_groq_client(settings=settings)
        logger.info("Groq client created")
        
        # 5. Initialize Groq model
        logger.info(" Creating Groq model...")
        _groq_model = create_groq_model(settings=settings)
        logger.info("Groq model created")
        
        # 6. Initialize AI agent with system prompt
        logger.info("Creating AI teacher agent...")
        groq_agent = create_groq_agent(
            groq_model=_groq_model,
            tools=[],
            system_prompt=(
                "You are a supportive teacher helping students understand and retain new concepts "
                "while practicing public speaking. "
                "Explain ideas clearly and simply, assuming the student may not know key terms. "
                "If you use a new concept, define it in plain language and give a quick example. "
                "Help students understand the main idea before details and connect new concepts "
                "to things they already know. "
                "Encourage students to practice explaining ideas out loud in their own words. "
                "If something seems unclear or confusing, slow down and re-explain it a different way. "
                "End each response with one or two quick recall questions or a short speaking exercise "
                "to help the student remember the concept."
            ),
        )
        logger.info("AI agent created")
        
        # 7. Store everything in app.state for dependency injection
        app.state.aiohttp_session = aiohttp_session
        app.state.groq_client = groq_client
        app.state.groq_agent = groq_agent
        
        logger.info("=" * 60)
        logger.info("APPLICATION STARTUP COMPLETE")
        logger.info("=" * 60)
        
        # Yield application state to FastAPI
        yield {
            "aiohttp_session": aiohttp_session,
            "groq_client": groq_client,
            "groq_agent": groq_agent,
        }
    
    except Exception as e:
        # Log startup errors with full traceback
        logger.error("=" * 60)
        logger.error(f"STARTUP ERROR: {type(e).__name__}: {e}")
        logger.error("=" * 60)
        import traceback
        traceback.print_exc()
        raise

    finally:
        # Cleanup resources on shutdown
        logger.info("=" * 60)
        logger.info("Shutting down application")
        logger.info("=" * 60)
        
        # Close aiohttp session
        if aiohttp_session:
            try:
                logger.info("Closing aiohttp session")
                await aiohttp_session.close()
                logger.info("Aiohttp session closed")
            except Exception as e:
                logger.error(f" Error closing aiohttp session: {e}")

        # Close Groq client
        if groq_client:
            try:
                logger.info("Closing Groq client")
                await groq_client.close()
                logger.info("Groq client closed")
            except Exception as e:
                logger.error(f"Error closing Groq client: {e}")
        
        logger.info("=" * 60)
        logger.info("✅ APPLICATION SHUTDOWN COMPLETE")
        logger.info("=" * 60)