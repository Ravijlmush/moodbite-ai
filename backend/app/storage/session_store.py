"""Session state store: Redis with automatic in-memory TTL fallback (Spec 02 & 06)."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.schemas.api import CartEntry
from app.schemas.catalog import ComboRecommendation
from app.schemas.context import UserContext


class SessionRecord(BaseModel):
    session_id: str
    user_context: UserContext
    chat_history: list[dict[str, str]] = Field(default_factory=list)
    last_recommendations: list[ComboRecommendation] = Field(default_factory=list)
    swap_drink_step: int = 0
    cart: list[CartEntry] = Field(default_factory=list)
    updated_at: float = Field(default_factory=time.time)

    def append_turn(self, role: str, content: str) -> None:
        self.chat_history.append({"role": role, "content": content})
        if len(self.chat_history) > 8:
            self.chat_history = self.chat_history[-8:]


class SessionStore(Protocol):
    backend_name: str

    async def get(self, session_id: str) -> SessionRecord | None: ...
    async def save(self, record: SessionRecord) -> None: ...
    async def delete(self, session_id: str) -> None: ...
    async def get_or_create(self, session_id: str) -> SessionRecord: ...


class InMemoryTTLSessionStore:
    """Thread/async-safe ephemeral store with 2-hour sliding TTL."""

    backend_name: str = "in_memory_ttl"

    def __init__(self, ttl_seconds: int = 7200) -> None:
        self.ttl_seconds = ttl_seconds
        self._data: dict[str, SessionRecord] = {}
        self._lock = asyncio.Lock()

    def _evict_expired(self, now: float) -> None:
        expired = [k for k, v in self._data.items() if now - v.updated_at > self.ttl_seconds]
        for key in expired:
            del self._data[key]

    async def get(self, session_id: str) -> SessionRecord | None:
        async with self._lock:
            now = time.time()
            self._evict_expired(now)
            rec = self._data.get(session_id)
            if rec is None:
                return None
            return rec.model_copy(deep=True)

    async def save(self, record: SessionRecord) -> None:
        async with self._lock:
            now = time.time()
            self._evict_expired(now)
            record.updated_at = now
            self._data[record.session_id] = record.model_copy(deep=True)

    async def delete(self, session_id: str) -> None:
        async with self._lock:
            self._data.pop(session_id, None)

    async def get_or_create(self, session_id: str) -> SessionRecord:
        existing = await self.get(session_id)
        if existing is not None:
            return existing
        fresh = SessionRecord(
            session_id=session_id,
            user_context=UserContext(session_id=session_id, turn_count=0),
        )
        await self.save(fresh)
        return fresh


class RedisSessionStore:
    """Redis-backed session store with transparent in-memory fallback if Redis is down."""

    def __init__(self, redis_url: str, ttl_seconds: int = 7200) -> None:
        self.redis_url = redis_url
        self.ttl_seconds = ttl_seconds
        self._fallback = InMemoryTTLSessionStore(ttl_seconds=ttl_seconds)
        self._redis: Any = None
        self.backend_name = "redis"
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(redis_url, decode_responses=True, socket_connect_timeout=0.5)
        except Exception:
            self._redis = None
            self.backend_name = "in_memory_fallback"

    def _key(self, session_id: str) -> str:
        return f"moodbite:session:{session_id}"

    async def get(self, session_id: str) -> SessionRecord | None:
        if self._redis is not None:
            try:
                raw = await self._redis.get(self._key(session_id))
                if raw:
                    return SessionRecord.model_validate_json(raw)
                return None
            except Exception:
                self.backend_name = "in_memory_fallback"
        return await self._fallback.get(session_id)

    async def save(self, record: SessionRecord) -> None:
        record.updated_at = time.time()
        if self._redis is not None:
            try:
                await self._redis.set(
                    self._key(record.session_id),
                    record.model_dump_json(),
                    ex=self.ttl_seconds,
                )
                return
            except Exception:
                self.backend_name = "in_memory_fallback"
        await self._fallback.save(record)

    async def delete(self, session_id: str) -> None:
        if self._redis is not None:
            try:
                await self._redis.delete(self._key(session_id))
            except Exception:
                pass
        await self._fallback.delete(session_id)

    async def get_or_create(self, session_id: str) -> SessionRecord:
        existing = await self.get(session_id)
        if existing is not None:
            return existing
        fresh = SessionRecord(
            session_id=session_id,
            user_context=UserContext(session_id=session_id, turn_count=0),
        )
        await self.save(fresh)
        return fresh


def build_session_store(redis_url: str, ttl_seconds: int = 7200) -> SessionStore:
    if redis_url.strip():
        return RedisSessionStore(redis_url=redis_url.strip(), ttl_seconds=ttl_seconds)
    return InMemoryTTLSessionStore(ttl_seconds=ttl_seconds)
