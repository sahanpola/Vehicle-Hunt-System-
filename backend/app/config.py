"""All settings and secrets are loaded from the .env file."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    openai_model: str = "gpt-5"

    tavily_api_key: str = ""

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""

    database_url: str = "sqlite:///./vehicle_agent.db"
    timezone: str = "Asia/Colombo"
    cors_origins: str = "http://localhost:5173"
    max_pages_per_site: int = 2  # result pages fetched from each site's own search (~25-40 cars per page)
    max_listings_per_site: int = 10  # Tavily web-search results, for sites without a URL builder
    max_listings_to_analyse: int = 25  # cap on cars sent to the LLM agents per run


@lru_cache
def get_settings() -> Settings:
    return Settings()
