import logging

from ..ops.dlq import persist_dlq
from ..ops.metrics import record_stage
from ..ops.reindex import run_reindex

log = logging.getLogger("worker.ops")


def handle(event: dict) -> None:
    """Consumes rag.dead-letter (persist) and obsidian.reindex.requested (run)."""
    if "source_topic" in event:
        persist_dlq(event)
        payload = event.get("payload") or {}
        record_stage(
            "failed",
            note_id=payload.get("note_id"),
            path=payload.get("path"),
            vault_id=payload.get("vault_id"),
            ok=False,
            error=event.get("error_type"),
            extra={"sourceTopic": event.get("source_topic")},
        )
        log.info("persisted DLQ event from %s", event.get("source_topic"))
    elif event.get("job_id"):
        run_reindex(event)
