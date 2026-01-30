from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    groq_api_key: str
    openai_api_key: str

    model_config = SettingsConfigDict(
        #look for .env file in project root
        env_file=".env",
        #use utf-8 encoding for .env file
        env_file_encoding="utf-8",
        #allow case insensitive env var names
        case_sensitive=False,
        #ignore extra fields in env vars
        extra="allow"
    )

#return cached settings instance
@lru_cache
def get_settings() -> Settings:
    return Settings()
