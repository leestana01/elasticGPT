import json
import logging

from ..cache.redis_client import get_redis
from ..events.ids import now_iso

log = logging.getLogger("ops.metrics")

EVENTS_KEY = "ops:events"
MAX_EVENTS = 200


def record_stage(stage: str, *, note_id=None, path=None, vault_id=None, ok=True, error=None, extra=None) -> None:
    """Append a pipeline stage event to a capped Redis list + bump a counter.

    Used for the Indexing Status view and metrics (US-08-06 / US-09-05).
    """
    r = get_redis()
    if r is None:
        return
    try:
        event = {
            "stage": stage,
            "noteId": note_id,
            "path": path,
            "vaultId": vault_id,
            "ok": ok,
            "error": error,
            "ts": now_iso(),
        }
        if extra:
            event.update(extra)
        r.lpush(EVENTS_KEY, json.dumps(event, ensure_ascii=False))
        r.ltrim(EVENTS_KEY, 0, MAX_EVENTS - 1)
        r.incr(f"ops:count:{stage}")
        if not ok:
            r.incr("ops:count:errors")
    except Exception:  # noqa: BLE001
        pass


def incr(counter: str, n: int = 1) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        r.incrby(f"ops:count:{counter}", n)
    except Exception:  # noqa: BLE001
        pass


def recent_events(limit: int = 50) -> list[dict]:
    r = get_redis()
    if r is None:
        return []
    try:
        return [json.loads(x) for x in r.lrange(EVENTS_KEY, 0, limit - 1)]
    except Exception:  # noqa: BLE001
        return []


def counters() -> dict:
    r = get_redis()
    if r is None:
        return {}
    try:
        keys = r.keys("ops:count:*")
        return {k.split(":")[-1]: int(r.get(k) or 0) for k in keys}
    except Exception:  # noqa: BLE001
        return {}
