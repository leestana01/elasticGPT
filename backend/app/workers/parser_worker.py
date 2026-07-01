import logging
import os

from ..es.indexer import get_note
from ..events.build import downstream_event
from ..events.schemas import FileChangedEvent
from ..kafka import topics as T
from ..kafka.consumer import PermanentError
from ..kafka.producer import publish
from ..obsidian.hashing import content_hash_bytes
from ..obsidian.parser import parse_markdown
from ..vault.registry import get_vault_path

log = logging.getLogger("worker.parser")


def _source_type(path: str) -> str:
    return "generated" if path.startswith("90_Generated") else "original"


def _folder(path: str) -> str:
    parts = path.split("/")
    return parts[0] if len(parts) > 1 else ""


def _next_version(note_id: str, content_hash: str) -> int:
    existing = get_note(note_id)
    if not existing:
        return 1
    current = existing.get("note_version", 1)
    return current if existing.get("content_hash") == content_hash else current + 1


def handle_file_changed(event: dict) -> None:
    try:
        fc = FileChangedEvent(**event)
    except Exception as e:  # noqa: BLE001
        raise PermanentError(f"invalid file.changed event: {e}")

    if fc.event_type == "FILE_DELETED":
        return  # deletions flow through obsidian.note.deleted to the indexing worker

    vault_path = get_vault_path(fc.vault_id)
    if not vault_path:
        raise PermanentError(f"unknown vault: {fc.vault_id}")

    abs_path = os.path.join(vault_path, fc.path)
    if not os.path.exists(abs_path):
        log.info("file no longer exists, skipping: %s", fc.path)
        return

    with open(abs_path, "rb") as f:
        raw_bytes = f.read()
    content_hash = content_hash_bytes(raw_bytes)
    parsed = parse_markdown(raw_bytes.decode("utf-8", errors="replace"), fc.path)

    note_id = f"{fc.vault_id}:{fc.path}"
    note_version = _next_version(note_id, content_hash)

    evt = downstream_event(
        event,
        {
            "note_id": note_id,
            "vault_id": fc.vault_id,
            "user_id": fc.user_id,
            "path": fc.path,
            "title": parsed["title"],
            "folder": _folder(fc.path),
            "tags": parsed["tags"],
            "outgoing_links": parsed["outgoing_links"],
            "frontmatter": parsed["frontmatter"],
            "source_type": _source_type(fc.path),
            "note_version": note_version,
            "content_hash": content_hash,
            "sections": parsed["sections"],
            "attachments": parsed["attachments"],
            "headings": parsed["headings"],
            "code_block_count": len(parsed["code_blocks"]),
        },
    )
    publish(T.NOTE_PARSED, evt, key=note_id)
    log.info("parsed %s v%d (%d sections)", fc.path, note_version, len(parsed["sections"]))
