from dataclasses import dataclass
from typing import Literal, TypeAlias

import aiohttp
from pydantic_ai import Agent, RunContext, Tool
from pydantic_ai.models.groq import GroqModel

from app.settings import Settings


@dataclass
# Define type aliases for clarity
class Dependencies:
    settings: Settings
    session: aiohttp.ClientSession

def create_groq_agent(
    groq_model: GroqModel,
    tools: list[Tool[Dependencies]],
    system_prompt: str,
) -> Agent[Dependencies]:
    # Create a Groq-powered AI agent.
    return Agent(
        model=groq_model,
        deps_type=Dependencies,
        system_prompt=system_prompt,
        tools=tools,
    )