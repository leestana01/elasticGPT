"""Maps a WORKER_TYPE to the topics it consumes and its handler.

Handlers are filled in per epic (parser/chunker/embedding/indexing in EPIC-03,
knowledge/note_update in EPIC-07). Until a handler is wired, the worker still
runs and stays healthy as a live consumer.
"""
import logging

from ..kafka import topics as T

log = logging.getLogger("workers.registry")


def _unimplemented(worker_type: str):
    def _handler(event: dict):
        log.debug("[%s] received event (handler not yet wired): %s", worker_type, event.get("event_id"))

    return _handler


def build_registry() -> dict:
    return {
        "parser": {"topics": [T.FILE_CHANGED], "group": "parser", "handler": _unimplemented("parser")},
        "chunker": {"topics": [T.NOTE_PARSED], "group": "chunker", "handler": _unimplemented("chunker")},
        "embedding": {"topics": [T.NOTE_CHUNKED], "group": "embedding", "handler": _unimplemented("embedding")},
        "indexing": {"topics": [T.CHUNK_EMBEDDED], "group": "indexing", "handler": _unimplemented("indexing")},
        "knowledge": {"topics": [T.ANSWER_GENERATED], "group": "knowledge", "handler": _unimplemented("knowledge")},
        "note_update": {
            "topics": [T.NOTE_UPDATE_APPROVED],
            "group": "note_update",
            "handler": _unimplemented("note_update"),
        },
    }
