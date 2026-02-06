"""Pheme configuration management."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM (Ollama API)
    ollama_host: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="qwen2.5:1.5b-instruct")

    # Email
    smtp_host: str = Field(default="smtp.gmail.com")
    smtp_port: int = Field(default=587)
    smtp_user: str = Field(default="")
    smtp_password: str = Field(default="")
    digest_recipient: str = Field(default="")

    # Schedule
    digest_cron_hour: int = Field(default=6)
    digest_cron_minute: int = Field(default=0)
    digest_timezone: str = Field(default="UTC")

    # API
    pheme_port: int = Field(default=8020)
    pheme_db_path: str = Field(default="./pheme.sqlite")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


_settings: Settings | None = None


def get_settings() -> Settings:
    """Get cached settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset settings (for testing)."""
    global _settings
    _settings = None
