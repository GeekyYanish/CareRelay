from __future__ import annotations

import json
from collections import deque
from functools import lru_cache
from typing import Any

import redis

from .core import get_settings


class ResilientEventTransport:
    """Publish to Redis when available and always retain an in-process fallback."""

    def __init__(self) -> None:
        settings = get_settings()
        self.redis = redis.Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=0.15,
            socket_timeout=0.15,
            decode_responses=True,
        )
        self.buffer: deque[dict[str, Any]] = deque(maxlen=500)
        self.last_transport = "in-process"

    def publish(self, tenant_id: str, envelope: dict[str, Any]) -> None:
        safe_envelope = {**envelope, "tenant_id": tenant_id}
        self.buffer.append(safe_envelope)
        try:
            self.redis.publish(
                f"carerelay:{tenant_id}:events",
                json.dumps(safe_envelope, separators=(",", ":")),
            )
            self.last_transport = "redis+in-process"
        except redis.RedisError:
            self.last_transport = "in-process"

    def status(self) -> dict[str, Any]:
        return {"active": self.last_transport, "buffered_events": len(self.buffer)}


@lru_cache
def get_event_transport() -> ResilientEventTransport:
    return ResilientEventTransport()
