import logging
import os
from datetime import datetime, timezone

from watchdog.events import FileSystemEventHandler
from watchdog.observers.polling import PollingObserver

from ..cache.redis_client import get_redis
from ..events.ids import new_id, now_iso
from ..kafka import topics as T
from ..kafka.producer import publish
from .hashing import content_hash_file

log = logging.getLogger("vault.watcher")


def _rel(vault_path: str, abs_path: str) -> str:
    return os.path.relpath(abs_path, vault_path)


def _mtime_iso(abs_path: str) -> str:
    try:
        return datetime.fromtimestamp(os.path.getmtime(abs_path), tz=timezone.utc).isoformat()
    except OSError:
        return now_iso()


def emit_change(vault: dict, event_type: str, abs_path: str, old_abs: str | None = None) -> bool:
    """Build and publish a file-change event. Returns True if published.

    Deduplicates identical (path, content_hash) so unchanged files are not
    re-emitted (US-02-02). Deletes go to the dedicated note.deleted topic.
    """
    if not abs_path.endswith(".md"):
        return False

    vault_path = vault["path"]
    vault_id = vault["vaultId"]
    rel_path = _rel(vault_path, abs_path)
    is_delete = event_type == "FILE_DELETED"

    chash = None
    if not is_delete and os.path.exists(abs_path):
        chash = content_hash_file(abs_path)

    redis = get_redis()
    dedup_key = f"watch:{vault_id}:{rel_path}"
    if not is_delete and chash and redis is not None:
        if redis.get(dedup_key) == chash:
            return False  # unchanged content, skip
        redis.set(dedup_key, chash)
    if is_delete and redis is not None:
        redis.delete(dedup_key)

    event = {
        "event_id": new_id("evt"),
        "event_type": event_type,
        "vault_id": vault_id,
        "user_id": vault.get("userId"),
        "path": rel_path,
        "old_path": _rel(vault_path, old_abs) if old_abs else None,
        "file_type": "markdown",
        "content_hash": chash,
        "modified_at": None if is_delete else _mtime_iso(abs_path),
        "detected_at": now_iso(),
        "schema_version": 1,
    }
    topic = T.NOTE_DELETED if is_delete else T.FILE_CHANGED
    publish(topic, event, key=f"{vault_id}:{rel_path}")
    log.info("emit %s %s", event_type, rel_path)
    return True


class VaultEventHandler(FileSystemEventHandler):
    def __init__(self, vault: dict):
        self.vault = vault

    def on_created(self, event):
        if not event.is_directory:
            emit_change(self.vault, "FILE_CREATED", event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            emit_change(self.vault, "FILE_UPDATED", event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            emit_change(self.vault, "FILE_DELETED", event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            # rename: index the new path (carrying old_path) and remove the old note
            emit_change(self.vault, "FILE_RENAMED", event.dest_path, old_abs=event.src_path)
            emit_change(self.vault, "FILE_DELETED", event.src_path)


def initial_scan(vault: dict) -> int:
    """Emit an upsert event for every existing .md note so the pipeline indexes
    the vault on first run. Dedup keeps repeated restarts idempotent."""
    count = 0
    for root, _dirs, files in os.walk(vault["path"]):
        for name in files:
            if name.endswith(".md"):
                if emit_change(vault, "FILE_UPDATED", os.path.join(root, name)):
                    count += 1
    log.info("initial scan vault=%s emitted=%d", vault["vaultId"], count)
    return count


def start_watching(vaults: list[dict]) -> PollingObserver:
    """Poll-based watching so it works over Docker bind mounts (macOS/Windows)."""
    observer = PollingObserver(timeout=2.0)
    for vault in vaults:
        if os.path.isdir(vault["path"]):
            observer.schedule(VaultEventHandler(vault), vault["path"], recursive=True)
            log.info("watching vault=%s path=%s", vault["vaultId"], vault["path"])
    observer.start()
    return observer
