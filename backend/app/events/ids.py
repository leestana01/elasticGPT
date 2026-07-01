import uuid
from datetime import datetime, timezone


def new_id(prefix: str) -> str:
    """Short, prefixed, collision-resistant id, e.g. evt_1f3a...."""
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
