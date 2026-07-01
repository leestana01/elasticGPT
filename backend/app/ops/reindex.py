import logging
import os
from datetime import datetime, timezone

from ..db.database import session_scope
from ..db.models import ReindexJob
from ..events.ids import new_id, now_iso
from ..kafka import topics as T
from ..kafka.producer import publish
from ..obsidian.hashing import content_hash_file
from ..vault.registry import get_vault_path

log = logging.getLogger("ops.reindex")


def _to_dict(j: ReindexJob) -> dict:
    return {
        "jobId": j.job_id,
        "vaultId": j.vault_id,
        "path": j.path,
        "reason": j.reason,
        "status": j.status,
        "noteCount": j.note_count,
        "errorMessage": j.error_message,
        "createdAt": j.created_at.isoformat() if j.created_at else None,
        "completedAt": j.completed_at.isoformat() if j.completed_at else None,
    }


def create_job(vault_id: str, path: str | None, reason: str | None) -> dict:
    job_id = new_id("rjob")
    with session_scope() as session:
        session.add(ReindexJob(job_id=job_id, vault_id=vault_id, path=path, reason=reason, status="RUNNING"))
    publish(
        T.REINDEX_REQUESTED,
        {"event_id": new_id("evt"), "schema_version": 1, "job_id": job_id,
         "vault_id": vault_id, "path": path, "reason": reason, "created_at": now_iso()},
        key=job_id,
    )
    return get_job(job_id)


def get_job(job_id: str) -> dict | None:
    with session_scope() as session:
        j = session.get(ReindexJob, job_id)
        return _to_dict(j) if j else None


def list_jobs(vault_id: str | None = None, limit: int = 20) -> list[dict]:
    with session_scope() as session:
        q = session.query(ReindexJob)
        if vault_id:
            q = q.filter(ReindexJob.vault_id == vault_id)
        return [_to_dict(j) for j in q.order_by(ReindexJob.created_at.desc()).limit(limit).all()]


def _finish(job_id: str, status: str, note_count: int, error: str | None = None) -> None:
    with session_scope() as session:
        j = session.get(ReindexJob, job_id)
        if j:
            j.status = status
            j.note_count = note_count
            j.error_message = error
            j.completed_at = datetime.now(timezone.utc)


def run_reindex(event: dict) -> None:
    """Re-emit file.changed for the target notes (bypassing the watcher dedup),
    so the whole ingestion pipeline reprocesses them. ES upserts keep search
    available throughout (US-09-04)."""
    job_id = event.get("job_id")
    vault_id = event.get("vault_id")
    path = event.get("path")
    vault_path = get_vault_path(vault_id)
    if not vault_path:
        _finish(job_id, "FAILED", 0, f"unknown vault {vault_id}")
        return

    try:
        if path:
            targets = [path]
        else:
            targets = []
            for root, _dirs, files in os.walk(vault_path):
                for f in files:
                    if f.endswith(".md"):
                        targets.append(os.path.relpath(os.path.join(root, f), vault_path))

        count = 0
        for rel in targets:
            abs_p = os.path.join(vault_path, rel)
            if not os.path.exists(abs_p):
                continue
            publish(
                T.FILE_CHANGED,
                {
                    "event_id": new_id("evt"),
                    "event_type": "FILE_UPDATED",
                    "vault_id": vault_id,
                    "user_id": None,
                    "path": rel,
                    "old_path": None,
                    "file_type": "markdown",
                    "content_hash": content_hash_file(abs_p),
                    "modified_at": now_iso(),
                    "detected_at": now_iso(),
                    "schema_version": 1,
                    "reindex": True,
                },
                key=f"{vault_id}:{rel}",
            )
            count += 1

        _finish(job_id, "COMPLETED", count)
        publish(
            T.REINDEX_COMPLETED,
            {"event_id": new_id("evt"), "schema_version": 1, "job_id": job_id,
             "vault_id": vault_id, "note_count": count, "created_at": now_iso()},
            key=job_id,
        )
        log.info("reindex job %s completed (%d notes)", job_id, count)
    except Exception as e:  # noqa: BLE001
        _finish(job_id, "FAILED", 0, str(e))
        log.exception("reindex job %s failed", job_id)
        raise
