import logging

from ..events.build import downstream_event, pick_meta
from ..events.schemas import NoteParsedEvent
from ..kafka import topics as T
from ..kafka.consumer import PermanentError
from ..kafka.producer import publish
from ..obsidian.chunker import chunk_note
from ..ops.metrics import record_stage

log = logging.getLogger("worker.chunker")


def handle_note_parsed(event: dict) -> None:
    try:
        np = NoteParsedEvent(**event)
    except Exception as e:  # noqa: BLE001
        raise PermanentError(f"invalid note.parsed event: {e}")

    ctx = {
        "vault_id": np.vault_id,
        "path": np.path,
        "title": np.title,
        "note_version": np.note_version,
    }
    chunks = chunk_note(np.sections, ctx)

    meta = pick_meta(event)
    evt = downstream_event(event, {**meta, "chunks": chunks, "chunk_count": len(chunks)})
    publish(T.NOTE_CHUNKED, evt, key=np.note_id)
    record_stage("chunked", note_id=np.note_id, path=np.path, vault_id=np.vault_id, extra={"chunkCount": len(chunks)})
    log.info("chunked %s v%d into %d chunks", np.path, np.note_version, len(chunks))
