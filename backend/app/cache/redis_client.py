import logging

import redis

from ..config import settings

log = logging.getLogger("cache.redis")

_client: "redis.Redis | None" = None


def get_redis() -> "redis.Redis | None":
    """Return a shared Redis client, or None if Redis is unreachable.

    Callers treat a None result as "cache miss" so the system degrades
    gracefully when Redis is unavailable.
    """
    global _client
    if _client is None:
        try:
            _client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
            _client.ping()
        except Exception as e:  # noqa: BLE001
            log.warning("redis unavailable: %s", e)
            _client = None
    return _client
