import logging

from ..events.ids import new_id, now_iso
from ..events.schemas import SCHEMA_VERSION
from ..kafka import topics as T
from ..kafka.consumer import PermanentError
from ..kafka.producer import publish
from ..note_update.applier import apply_candidate
from ..note_update.repo import get_candidate, mark_applied

log = logging.getLogger("worker.note_update")


def handle_approved(event: dict) -> None:
    candidate_id = event.get("candidateId")
    if not candidate_id:
        raise PermanentError("approved event missing candidateId")

    current = get_candidate(candidate_id)
    if current and current["status"] == "APPLIED":
        log.info("candidate %s already applied, skip", candidate_id)
        return

    result = apply_candidate(event)
    mark_applied(candidate_id)

    publish(
        T.NOTE_UPDATED,
        {
            "event_id": new_id("evt"),
            "schema_version": SCHEMA_VERSION,
            "candidate_id": candidate_id,
            "vault_id": event.get("vaultId"),
            "path": result["path"],
            "action": result["action"],
            "created_at": now_iso(),
        },
        key=candidate_id,
    )
    log.info("applied %s → %s (%s)", candidate_id, result["path"], result["action"])
