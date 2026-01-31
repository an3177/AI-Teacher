
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API Keys which are used for external services
    groq_api_key: str
    
    database_url: str
    # Other settings can be added here as needed
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow"
    )


@lru_cache
def get_settings() -> Settings:
    #Get the application settings
    return Settings()