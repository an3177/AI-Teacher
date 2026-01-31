
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API Keys (required)
    groq_api_key: str
    openai_api_key: str
    
    database_url: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow"
    )


@lru_cache
def get_settings() -> Settings:
    """Get the application settings singleton."""
    return Settings()