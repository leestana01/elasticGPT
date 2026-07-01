import logging

from ..es.client import get_es
from ..es.indexer import (
    delete_stale_chunks,
    index_chunks,
    index_edges,
    index_note,
    resolve_incoming_edges,
    soft_delete_note,
)
from ..es.indices import write_alias
from ..events.build import downstream_event, pick_meta
from ..kafka import topics as T
from ..kafka.consumer import PermanentError
from ..kafka.producer import publish

log = logging.getLogger("worker.indexing")


def handle(event: dict) -> None:
    """Consumes both chunk.embedded (index) and note.deleted (soft delete)."""
    if event.get("event_type") == "FILE_DELETED":
        note_id = f"{event['vault_id']}:{event['path']}"
        soft_delete_note(note_id)
        log.info("soft-deleted note %s", note_id)
        return

    chunks = event.get("chunks")
    if not isinstance(chunks, list) or not chunks:
        raise PermanentError("chunk.embedded event has no chunks")
    if any(c.get("content_vector") is None for c in chunks):
        raise PermanentError("chunk missing embedding vector")

    meta = pick_meta(event)
    ids = index_chunks(chunks, meta)
    index_note(meta, len(ids))
    index_edges(meta)
    resolve_incoming_edges(meta)
    delete_stale_chunks(meta["note_id"], meta["note_version"])
    get_es().indices.refresh(index=write_alias("chunks"))

    evt = downstream_event(
        event,
        {
            "note_id": meta["note_id"],
            "vault_id": meta["vault_id"],
            "path": meta["path"],
            "note_version": meta["note_version"],
            "chunk_count": len(ids),
            "chunk_ids": ids,
        },
    )
    publish(T.CHUNK_INDEXED, evt, key=meta["note_id"])
    log.info("indexed %s v%s: %d chunks", meta["path"], meta["note_version"], len(ids))
