"""Shared pytest fixtures for MoodBite AI test suite."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture()
def offline_settings() -> Settings:
    return Settings(
        llm_provider="offline",
        openrouter_api_key="",
        openai_api_key="",
        gemini_api_key="",
        database_url="",
        redis_url="",
        daily_request_limit=20,
        rate_limit_persist_path="",
    )


@pytest.fixture()
def client(offline_settings: Settings) -> TestClient:
    app = create_app(offline_settings)
    with TestClient(app) as test_client:
        yield test_client
