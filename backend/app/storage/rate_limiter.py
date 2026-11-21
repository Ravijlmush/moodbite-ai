"""Daily request quota limiter (default: 20 requests per UTC day)."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RateLimitStatus:
    allowed: bool
    limit: int
    used: int
    remaining: int
    reset_at: str


def _today_key_and_reset() -> tuple[str, str, int]:
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    ttl_secs = max(60, int((next_midnight - now).total_seconds()))
    return today, next_midnight.isoformat(), ttl_secs


class DailyRateLimiter:
    """Enforces a strict per-day request cap across chat turns (Redis or local/memory)."""

    def __init__(
        self,
        *,
        limit: int = 20,
        redis_url: str = "",
        persist_path: str = "",
    ) -> None:
        self.limit = max(1, limit)
        self.persist_path = Path(persist_path) if persist_path.strip() else None
        self._lock = asyncio.Lock()
        self._counts: dict[str, int] = {}
        self._redis: Any = None

        if redis_url.strip():
            try:
                import redis.asyncio as aioredis

                self._redis = aioredis.from_url(
                    redis_url.strip(),
                    decode_responses=True,
                    socket_connect_timeout=0.5,
                )
            except Exception:
                self._redis = None

        self._load_persisted()

    def _load_persisted(self) -> None:
        if self.persist_path is None or not self.persist_path.exists():
            return
        try:
            data = json.loads(self.persist_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self._counts = {str(k): int(v) for k, v in data.items()}
        except Exception:
            self._counts = {}

    def _save_persisted(self) -> None:
        if self.persist_path is None:
            return
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)
            self.persist_path.write_text(
                json.dumps(self._counts, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _redis_key(self, day: str) -> str:
        return f"moodbite:daily_requests:{day}"

    async def peek(self) -> RateLimitStatus:
        day, reset_at, _ = _today_key_and_reset()
        if self._redis is not None:
            try:
                raw = await self._redis.get(self._redis_key(day))
                used = int(raw) if raw is not None else 0
                remaining = max(0, self.limit - used)
                return RateLimitStatus(
                    allowed=used < self.limit,
                    limit=self.limit,
                    used=used,
                    remaining=remaining,
                    reset_at=reset_at,
                )
            except Exception:
                pass

        async with self._lock:
            used = self._counts.get(day, 0)
            remaining = max(0, self.limit - used)
            return RateLimitStatus(
                allowed=used < self.limit,
                limit=self.limit,
                used=used,
                remaining=remaining,
                reset_at=reset_at,
            )

    async def consume(self) -> RateLimitStatus:
        day, reset_at, ttl_secs = _today_key_and_reset()
        if self._redis is not None:
            try:
                key = self._redis_key(day)
                current = await self._redis.get(key)
                used_before = int(current) if current is not None else 0
                if used_before >= self.limit:
                    return RateLimitStatus(
                        allowed=False,
                        limit=self.limit,
                        used=used_before,
                        remaining=0,
                        reset_at=reset_at,
                    )
                used = int(await self._redis.incr(key))
                if used == 1:
                    await self._redis.expire(key, ttl_secs)
                if used > self.limit:
                    await self._redis.decr(key)
                    return RateLimitStatus(
                        allowed=False,
                        limit=self.limit,
                        used=self.limit,
                        remaining=0,
                        reset_at=reset_at,
                    )
                return RateLimitStatus(
                    allowed=True,
                    limit=self.limit,
                    used=used,
                    remaining=max(0, self.limit - used),
                    reset_at=reset_at,
                )
            except Exception:
                pass

        async with self._lock:
            used_before = self._counts.get(day, 0)
            if used_before >= self.limit:
                return RateLimitStatus(
                    allowed=False,
                    limit=self.limit,
                    used=used_before,
                    remaining=0,
                    reset_at=reset_at,
                )
            used = used_before + 1
            self._counts = {day: used}
            self._save_persisted()
            return RateLimitStatus(
                allowed=True,
                limit=self.limit,
                used=used,
                remaining=max(0, self.limit - used),
                reset_at=reset_at,
            )
