"""Conversational chat turn, SSE streaming, refinement, and session endpoints."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sse_starlette.sse import EventSourceResponse

from app.api.deps import AppContainer, get_container
from app.prompts.templates import LOADING_MICRO_COPY
from app.schemas.api import (
    CartResponse,
    ChatRefineRequest,
    ChatTurnRequest,
    ChatTurnResponse,
    SessionDetailResponse,
)

router = APIRouter(prefix="/api/v1", tags=["chat"])


async def _enforce_daily_quota(container: AppContainer) -> dict[str, str]:
    quota = await container.rate_limiter.consume()
    headers = {
        "X-RateLimit-Limit": str(quota.limit),
        "X-RateLimit-Remaining": str(quota.remaining),
        "X-RateLimit-Reset": quota.reset_at,
    }
    if not quota.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "DAILY_LIMIT_REACHED",
                "message": f"Daily request limit reached ({quota.used}/{quota.limit}). Resets at midnight UTC.",
                "limit": quota.limit,
                "used": quota.used,
                "remaining": 0,
                "reset_at": quota.reset_at,
            },
            headers=headers,
        )
    return headers


@router.post("/chat/turn", response_model=ChatTurnResponse)
async def chat_turn(
    payload: ChatTurnRequest,
    response: Response,
    container: AppContainer = Depends(get_container),
) -> ChatTurnResponse:
    quota_headers = await _enforce_daily_quota(container)
    for k, v in quota_headers.items():
        response.headers[k] = v
    return await container.orchestrator.handle_turn(payload)


@router.post("/chat/turn/stream")
async def chat_turn_stream(
    payload: ChatTurnRequest,
    container: AppContainer = Depends(get_container),
) -> EventSourceResponse:
    quota_headers = await _enforce_daily_quota(container)

    async def event_generator() -> AsyncGenerator[dict[str, str], None]:
        yield {
            "event": "status",
            "data": json.dumps({"message": LOADING_MICRO_COPY[0]}, ensure_ascii=False),
        }
        task = asyncio.create_task(container.orchestrator.handle_turn(payload))

        idx = 1
        while not task.done():
            await asyncio.sleep(0.15)
            if not task.done() and idx < len(LOADING_MICRO_COPY):
                yield {
                    "event": "status",
                    "data": json.dumps({"message": LOADING_MICRO_COPY[idx]}, ensure_ascii=False),
                }
                idx += 1

        response = await task

        # Stream agent_message tokens smoothly for crisp monochrome chat UX
        words = response.agent_message.split(" ")
        chunk_size = 3
        for start in range(0, len(words), chunk_size):
            chunk = " ".join(words[start : start + chunk_size])
            suffix = " " if start + chunk_size < len(words) else ""
            yield {
                "event": "token",
                "data": json.dumps({"text": chunk + suffix}, ensure_ascii=False),
            }
            await asyncio.sleep(0.015)

        if response.recommendations:
            yield {
                "event": "recommendations",
                "data": json.dumps(
                    [r.model_dump() for r in response.recommendations],
                    ensure_ascii=False,
                ),
            }

        yield {
            "event": "done",
            "data": response.model_dump_json(),
        }

    return EventSourceResponse(event_generator(), headers=quota_headers)


@router.post("/chat/refine", response_model=ChatTurnResponse)
async def chat_refine(
    payload: ChatRefineRequest,
    container: AppContainer = Depends(get_container),
) -> ChatTurnResponse:
    return await container.orchestrator.handle_refine(payload)


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(
    session_id: str,
    container: AppContainer = Depends(get_container),
) -> SessionDetailResponse:
    record = await container.session_store.get(session_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SESSION_NOT_FOUND", "message": f"Session '{session_id}' not found."},
        )
    cart_total_items = sum(entry.quantity for entry in record.cart)
    cart_total_price = sum(entry.line_total_inr for entry in record.cart)
    return SessionDetailResponse(
        session_id=record.session_id,
        turn_count=record.user_context.turn_count,
        user_context=record.user_context,
        chat_history=record.chat_history,
        recommendations=record.last_recommendations,
        cart=CartResponse(
            session_id=record.session_id,
            items=record.cart,
            total_items=cart_total_items,
            total_price_inr=cart_total_price,
        ),
    )


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    container: AppContainer = Depends(get_container),
) -> dict[str, str]:
    await container.session_store.delete(session_id)
    return {"status": "deleted", "session_id": session_id}
