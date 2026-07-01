"""Maps a WORKER_TYPE to the topics it consumes and its handler."""
import logging

from ..kafka import topics as T

log = logging.getLogger("workers.registry")


def _unimplemented(worker_type: str):
    def _handler(event: dict):
        log.debug("[%s] received event (handler not yet wired): %s", worker_type, event.get("event_id"))

    return _handler


def build_registry() -> dict:
    from .chunker_worker import handle_note_parsed
    from .embedding_worker import handle_note_chunked
    from .indexing_worker import handle as handle_indexing
    from .parser_worker import handle_file_changed

    return {
        "parser": {"topics": [T.FILE_CHANGED], "group": "parser", "handler": handle_file_changed},
        "chunker": {"topics": [T.NOTE_PARSED], "group": "chunker", "handler": handle_note_parsed},
        "embedding": {"topics": [T.NOTE_CHUNKED], "group": "embedding", "handler": handle_note_chunked},
        "indexing": {
            "topics": [T.CHUNK_EMBEDDED, T.NOTE_DELETED],
            "group": "indexing",
            "handler": handle_indexing,
        },
        # implemented in EPIC-07
        "knowledge": {"topics": [T.ANSWER_GENERATED], "group": "knowledge", "handler": _unimplemented("knowledge")},
        "note_update": {
            "topics": [T.NOTE_UPDATE_APPROVED],
            "group": "note_update",
            "handler": _unimplemented("note_update"),
        },
    }
