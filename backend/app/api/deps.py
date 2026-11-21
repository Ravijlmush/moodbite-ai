"""FastAPI dependency container and singleton wiring."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from app.agent.state_machine import MoodBiteOrchestrator
from app.config import Settings, get_settings
from app.mcp.swiggy_oauth import SwiggyOAuthClient, SwiggyTokenStore
from app.recommender.catalog_repo import (
    CatalogRepository,
    LocalJsonCatalogRepository,
    PostgresPgVectorCatalogRepository,
)
from app.recommender.embeddings import EmbeddingService
from app.recommender.engine import RecommendationEngine
from app.recommender.swiggy_live_ranker import SwiggyLiveRanker
from app.storage.rate_limiter import DailyRateLimiter
from app.storage.session_store import SessionStore, build_session_store


@dataclass
class AppContainer:
    settings: Settings
    session_store: SessionStore
    rate_limiter: DailyRateLimiter
    catalog: CatalogRepository
    engine: RecommendationEngine
    swiggy_tokens: SwiggyTokenStore
    swiggy_oauth: SwiggyOAuthClient
    swiggy_ranker: SwiggyLiveRanker
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
    swiggy_tokens = SwiggyTokenStore()
    swiggy_oauth = SwiggyOAuthClient(
        mcp_url=cfg.swiggy_mcp_url,
        redirect_uri=cfg.swiggy_oauth_redirect_uri,
        configured_client_id=cfg.swiggy_client_id,
    )
    swiggy_ranker = SwiggyLiveRanker(embedder=embedder)
    orchestrator = MoodBiteOrchestrator(
        settings=cfg,
        session_store=session_store,
        catalog=catalog,
        engine=engine,
        swiggy_tokens=swiggy_tokens,
        swiggy_ranker=swiggy_ranker,
    )
    return AppContainer(
        settings=cfg,
        session_store=session_store,
        rate_limiter=rate_limiter,
        catalog=catalog,
        engine=engine,
        swiggy_tokens=swiggy_tokens,
        swiggy_oauth=swiggy_oauth,
        swiggy_ranker=swiggy_ranker,
        orchestrator=orchestrator,
    )


def get_container(request: Request) -> AppContainer:
    return request.app.state.container
