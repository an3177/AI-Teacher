from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    groq_api_key: str
    openai_api_key: str

    # Database URL (Railway will provide this automatically)
    database_url: str = "sqlite:///./ai_friend.db"  # Default fallback for local dev

    model_config = SettingsConfigDict(
        # Look for .env file in project root
        env_file=".env",
        # Use utf-8 encoding for .env file
        env_file_encoding="utf-8",
        # Allow case insensitive env var names
        case_sensitive=False,
        # Ignore extra fields in env vars
        extra="allow"
    )


# Return cached settings instance
@lru_cache
def get_settings() -> Settings:
    return Settings()

@lru_cache
def get_settings() -> Settings:
    return Settings()