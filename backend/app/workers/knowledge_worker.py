import logging

from ..es.indexer import index_qa_knowledge
from ..events.ids import new_id, now_iso
from ..events.schemas import SCHEMA_VERSION
from ..kafka import topics as T
from ..kafka.producer import publish
from ..knowledge.extractor import extract
from ..note_update.repo import create_candidate

log = logging.getLogger("worker.knowledge")


def handle_answer_generated(event: dict) -> None:
    data = extract(event)
    if not data:
        log.info("nothing worth saving for query=%s", event.get("query_id"))
        return

    created = create_candidate(data)
    if not created:
        log.info("duplicate candidate, skip (query=%s)", event.get("query_id"))
        return

    publish(
        T.NOTE_UPDATE_REQUESTED,
        {
            "event_id": new_id("evt"),
            "schema_version": SCHEMA_VERSION,
            "requires_approval": True,
            "created_at": now_iso(),
            **created,
        },
        key=created["candidateId"],
    )
    try:
        index_qa_knowledge(created)
    except Exception:  # noqa: BLE001
        log.exception("qa knowledge index failed")

    log.info(
        "candidate %s (%s → %s)",
        created["candidateId"], created["candidateType"], created["targetNotePath"],
    )
