from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import redis

from .core import get_settings


class ReportListCache:
    """Short-TTL Redis cache for clinician report list queries (tenant scoped)."""

    ttl_seconds = 20

    def __init__(self) -> None:
        settings = get_settings()
        self.redis = redis.Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=0.15,
            socket_timeout=0.15,
            decode_responses=True,
        )

    def _key(self, tenant_id: str, fingerprint: str) -> str:
        return f"carerelay:{tenant_id}:reports:{fingerprint}"

    def get(self, tenant_id: str, fingerprint: str) -> dict[str, Any] | None:
        try:
            raw = self.redis.get(self._key(tenant_id, fingerprint))
            return json.loads(raw) if raw else None
        except (redis.RedisError, json.JSONDecodeError):
            return None

    def set(self, tenant_id: str, fingerprint: str, payload: dict[str, Any]) -> None:
        try:
            self.redis.setex(
                self._key(tenant_id, fingerprint),
                self.ttl_seconds,
                json.dumps(payload, separators=(",", ":"), default=str),
            )
        except redis.RedisError:
            return

    def invalidate_tenant(self, tenant_id: str) -> None:
        try:
            for key in self.redis.scan_iter(match=f"carerelay:{tenant_id}:reports:*", count=100):
                self.redis.delete(key)
        except redis.RedisError:
            return


@lru_cache
def get_report_list_cache() -> ReportListCache:
    return ReportListCache()
