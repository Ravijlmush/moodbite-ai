"""FastAPI dependency container and singleton wiring."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from app.agent.state_machine import MoodBiteOrchestrator
from app.config import Settings, get_settings
from app.recommender.catalog_repo import (
    CatalogRepository,
    LocalJsonCatalogRepository,
    PostgresPgVectorCatalogRepository,
)
from app.recommender.embeddings import EmbeddingService
from app.recommender.engine import RecommendationEngine
from app.storage.rate_limiter import DailyRateLimiter
from app.storage.session_store import SessionStore, build_session_store


@dataclass
class AppContainer:
    settings: Settings
    session_store: SessionStore
    rate_limiter: DailyRateLimiter
    catalog: CatalogRepository
    engine: RecommendationEngine
    orchestrator: MoodBiteOrchestrator


def build_container(settings: Settings | None = None) -> AppContainer:
    cfg = settings or get_settings()
    embedder = EmbeddingService(
        provider=cfg.embedding_provider,
        openai_api_key=cfg.openai_api_key,
        openai_base_url=cfg.openai_base_url,
    )
    if cfg.database_url.strip():
        catalog: CatalogRepository = PostgresPgVectorCatalogRepository(
            database_url=cfg.database_url.strip(),
            catalog_path=cfg.catalog_path,
            embedder=embedder,
        )
    else:
        catalog = LocalJsonCatalogRepository(
            catalog_path=cfg.catalog_path,
            embedder=embedder,
        )

    session_store = build_session_store(
        redis_url=cfg.redis_url,
        ttl_seconds=cfg.session_ttl_seconds,
    )
    rate_limiter = DailyRateLimiter(
        limit=cfg.daily_request_limit,
        redis_url=cfg.redis_url,
        persist_path=cfg.rate_limit_persist_path,
    )
    engine = RecommendationEngine(catalog=catalog, embedder=embedder)
    orchestrator = MoodBiteOrchestrator(
        settings=cfg,
        session_store=session_store,
        catalog=catalog,
        engine=engine,
    )
    return AppContainer(
        settings=cfg,
        session_store=session_store,
        rate_limiter=rate_limiter,
        catalog=catalog,
        engine=engine,
        orchestrator=orchestrator,
    )


def get_container(request: Request) -> AppContainer:
    return request.app.state.container
