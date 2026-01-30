from contextlib import asynccontextmanager
from typing import AsyncIterator, TypedDict
import logging

import aiohttp
from fastapi import FastAPI
from groq import AsyncGroq
from openai import AsyncOpenAI
from pydantic_ai import Agent
from pydantic_ai.models.groq import GroqModel
from pydantic_ai.providers.groq import GroqProvider

from app.llm import Dependencies, create_groq_agent
from app.settings import Settings, get_settings

logger = logging.getLogger(__name__)

#Create aiohttp ClientSession
def create_aiohttp_session() -> aiohttp.ClientSession:
    return aiohttp.ClientSession()

# Create Groq client
def create_groq_client(
    settings: Settings,
) -> AsyncGroq:
    return AsyncGroq(api_key=settings.groq_api_key)

# Create OpenAI client
def create_openai_client(
    settings: Settings,
) -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.openai_api_key)

# Create Groq model
def create_groq_model(
    settings: Settings,
) -> GroqModel:
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
#FastAPI lifespan manager
async def app_lifespan(app: FastAPI) -> AsyncIterator[State]:
    logger.info("Starting up application...")
    settings = get_settings()
    
    try:
        #Initialize resources
        aiohttp_session = create_aiohttp_session()
        openai_client = create_openai_client(settings=settings)
        groq_client = create_groq_client(settings=settings)
        _groq_model = create_groq_model(settings=settings)
        groq_agent = create_groq_agent(
            groq_model=_groq_model,
            tools=[],
            system_prompt=(
                "You are a supportive teacher helping students understand and retain new concepts while practicing public speaking."
                "Explain ideas clearly and simply, assuming the student may not know key terms."
                "If you use a new concept, define it in plain language and give a quick example."
                "Help students understand the main idea before details and connect new concepts to things they already know."
                "Encourage students to practice explaining ideas out loud in their own words."
                "If something seems unclear or confusing, slow down and re-explain it a different way."
                "End each response with one or two quick recall questions or a short speaking exercise to help the student remember the concept."
            ),
        )
        
        # Store in app.state
        app.state.aiohttp_session = aiohttp_session
        app.state.openai_client = openai_client
        app.state.groq_client = groq_client
        app.state.groq_agent = groq_agent
        
        logger.info("Application startup complete")
        #yield application state
        yield {
            "aiohttp_session": aiohttp_session,
            "openai_client": openai_client,
            "groq_client": groq_client,
            "groq_agent": groq_agent,
        }
    
    except Exception as e:
        #log startup errors
        logger.error(f"Startup error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise

    finally:
        #cleanup resources on shutdown
        logger.info("Closing aiohttp session")
        await aiohttp_session.close()

        logger.info("Closing OpenAI client")
        await openai_client.close()

        logger.info("Closing Groq client")
        await groq_client.close()
        
        logger.info("Application shutdown complete")