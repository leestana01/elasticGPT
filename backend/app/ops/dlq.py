from ..db.database import session_scope
from ..db.models import DlqEvent
from ..kafka.producer import publish


def _to_dict(d: DlqEvent) -> dict:
    return {
        "dlqId": d.dlq_id,
        "sourceTopic": d.source_topic,
        "consumerGroup": d.consumer_group,
        "errorType": d.error_type,
        "errorMessage": d.error_message,
        "retryCount": d.retry_count,
        "payload": d.payload or {},
        "status": d.status,
        "createdAt": d.created_at.isoformat() if d.created_at else None,
    }


def persist_dlq(event: dict) -> None:
    with session_scope() as session:
        if session.get(DlqEvent, event.get("event_id")):
            return
        session.add(
            DlqEvent(
                dlq_id=event.get("event_id"),
                source_topic=event.get("source_topic", ""),
                consumer_group=event.get("consumer_group", ""),
                error_type=event.get("error_type", ""),
                error_message=event.get("error_message", ""),
                retry_count=event.get("retry_count", 0),
                payload=event.get("payload", {}),
                status="NEW",
            )
        )


def list_dlq(status: str | None = None) -> list[dict]:
    with session_scope() as session:
        q = session.query(DlqEvent)
        if status:
            q = q.filter(DlqEvent.status == status)
        return [_to_dict(d) for d in q.order_by(DlqEvent.created_at.desc()).all()]


def count_dlq(status: str | None = "NEW") -> int:
    with session_scope() as session:
        q = session.query(DlqEvent)
        if status:
            q = q.filter(DlqEvent.status == status)
        return q.count()


def reprocess(dlq_id: str) -> dict | None:
    """Republish the original payload to its source topic so the owning worker
    retries it, then mark the DLQ record reprocessed (US-09-02)."""
    with session_scope() as session:
        d = session.get(DlqEvent, dlq_id)
        if d is None or d.status == "REPROCESSED":
            return None
        payload = d.payload or {}
        key = payload.get("event_id") if isinstance(payload, dict) else None
        publish(d.source_topic, payload, key=key)
        d.status = "REPROCESSED"
        return _to_dict(d)
