"""FastAPI application entry point for MoodBite AI."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.deps import AppContainer, build_container
from app.api.routes_cart import router as cart_router
from app.api.routes_chat import router as chat_router
from app.api.routes_health import router as health_router
from app.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app_instance: FastAPI):
        if not hasattr(app_instance.state, "container") or app_instance.state.container is None:
            app_instance.state.container = build_container(cfg)
        yield

    app = FastAPI(
        title=cfg.app_name,
        version=cfg.app_version,
        description="Conversational mood-based food delivery concierge (hybrid LLM + deterministic ranking).",
        lifespan=lifespan,
    )
    # Pre-initialize container synchronously so TestClient works both with and without lifespan
    app.state.container: AppContainer = build_container(cfg)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-Process-Time-Ms",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ],
    )

    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next) -> Response:
        t0 = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
        return response

    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(cart_router)
    return app


app = create_app()
