from .ids import new_id

NOTE_META_KEYS = [
    "note_id",
    "vault_id",
    "user_id",
    "path",
    "title",
    "folder",
    "tags",
    "outgoing_links",
    "source_type",
    "note_version",
    "content_hash",
    "frontmatter",
]


def pick_meta(d: dict) -> dict:
    return {k: d.get(k) for k in NOTE_META_KEYS}


def downstream_event(prev: dict, extra: dict) -> dict:
    """Create a new event that traces back to ``prev`` via source_event_id."""
    evt = {
        "event_id": new_id("evt"),
        "source_event_id": prev.get("event_id"),
        "schema_version": prev.get("schema_version", 1),
    }
    evt.update(extra)
    return evt
