"""Application configuration loaded cleanly from environment variables / .env files."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Runtime settings for MoodBite AI loaded via pydantic-settings."""

    model_config = SettingsConfigDict(
        env_file=(str(ROOT_DIR / ".env"), str(BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "MoodBite AI"
    app_version: str = "0.1.0"
    llm_provider: Literal["auto", "openrouter", "openai", "gemini", "ollama", "offline"] = "auto"

    openrouter_api_key: str = ""
    openrouter_model: str = "openai/gpt-4o-mini"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_site_url: str = "http://localhost:3000"
    openrouter_app_name: str = "MoodBite AI"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    llm_timeout_secs: float = 2.5
    embedding_provider: Literal["local_semantic", "openai"] = "local_semantic"

    database_url: str = ""
    redis_url: str = ""
    session_ttl_seconds: int = 7200  # 2-hour TTL (Spec 02)
    daily_request_limit: int = 20
    rate_limit_persist_path: str = ""

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    catalog_path: str = str(BACKEND_DIR / "data" / "catalog.json")

    default_lat: float = 28.6139
    default_lng: float = 77.2090

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def resolved_llm_provider(self) -> Literal["openrouter", "openai", "gemini", "ollama", "offline"]:
        """Resolve active LLM provider without ever requiring keys to boot."""
        if self.llm_provider == "offline":
            return "offline"
        if self.llm_provider == "openrouter":
            return "openrouter" if self.openrouter_api_key.strip() else "offline"
        if self.llm_provider == "openai":
            return "openai" if self.openai_api_key.strip() else "offline"
        if self.llm_provider == "gemini":
            return "gemini" if self.gemini_api_key.strip() else "offline"
        if self.llm_provider == "ollama":
            return "ollama"

        # auto mode
        if self.openrouter_api_key.strip():
            return "openrouter"
        if self.openai_api_key.strip():
            return "openai"
        if self.gemini_api_key.strip():
            return "gemini"
        return "offline"


def get_settings() -> Settings:
    return Settings()
