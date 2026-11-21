"""Health, catalog, and stress-report inspection endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import AppContainer, get_container
from app.schemas.api import CatalogStatsResponse, HealthResponse

router = APIRouter(tags=["health"])
STRESS_REPORT_PATH = Path(__file__).resolve().parents[2] / "evals" / "stress_suite_report.json"


@router.get("/health", response_model=HealthResponse)
async def health_check(container: AppContainer = Depends(get_container)) -> HealthResponse:
    stats = container.catalog.get_stats()
    quota = await container.rate_limiter.peek()
    return HealthResponse(
        status="ok",
        app=container.settings.app_name,
        version=container.settings.app_version,
        llm_provider=container.settings.resolved_llm_provider(),
        catalog_restaurants=stats.total_restaurants,
        catalog_items=stats.total_items,
        storage_backend=container.session_store.backend_name,
        catalog_backend=container.catalog.backend_name,
        daily_request_limit=quota.limit,
        daily_requests_used=quota.used,
        daily_requests_remaining=quota.remaining,
        swiggy_mcp_connected=container.swiggy_tokens.is_connected,
        swiggy_mcp_url=container.settings.swiggy_mcp_url,
    )


@router.get("/api/v1/catalog/stats", response_model=CatalogStatsResponse)
async def catalog_stats(container: AppContainer = Depends(get_container)) -> CatalogStatsResponse:
    return container.catalog.get_stats()


@router.get("/api/v1/stress-report")
async def stress_report() -> dict[str, Any]:
    """Return the committed 30-prompt adversarial & load stress suite report."""
    if not STRESS_REPORT_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "STRESS_REPORT_NOT_FOUND", "message": "Stress report JSON not found."},
        )
    return json.loads(STRESS_REPORT_PATH.read_text(encoding="utf-8"))
