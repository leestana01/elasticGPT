import logging

from fastapi import APIRouter
from pydantic import BaseModel

from ..config import settings
from ..db.database import session_scope
from ..db.models import Feedback
from ..events.ids import new_id, now_iso
from ..events.schemas import SCHEMA_VERSION
from ..kafka import topics as T
from ..kafka.producer import publish
from ..knowledge.extractor import build_correction
from ..note_update.repo import create_candidate, reject_pending_for_query
from ..rag.query_logs import get_query_log

router = APIRouter(prefix="/api/feedback", tags=["feedback"])
log = logging.getLogger("api.feedback")


class FeedbackRequest(BaseModel):
    queryId: str | None = None
    answerId: str | None = None
    vaultId: str | None = None
    vote: str | None = None  # up | down
    comment: str | None = None
    citationCorrect: bool | None = None


def _handle_correction(query_id: str, comment: str) -> dict | None:
    """A down-vote with a correction comment turns into a correction candidate,
    and auto-rejects any pending auto-save candidate for that query (US-07-07)."""
    with session_scope() as _s:
        rejected = reject_pending_for_query(query_id)
    log.info("auto-rejected %d pending candidate(s) for %s", rejected, query_id)
    if not comment:
        return None
    query_log = get_query_log(query_id)
    if not query_log:
        return None
    data = build_correction(query_log, comment)
    created = create_candidate(data)
    if created:
        publish(
            T.NOTE_UPDATE_REQUESTED,
            {"event_id": new_id("evt"), "schema_version": SCHEMA_VERSION, "requires_approval": True,
             "created_at": now_iso(), **created},
            key=created["candidateId"],
        )
    return created


@router.post("")
def api_feedback(req: FeedbackRequest) -> dict:
    feedback_id = new_id("fb")
    with session_scope() as session:
        session.add(
            Feedback(
                feedback_id=feedback_id,
                query_id=req.queryId,
                answer_id=req.answerId,
                vault_id=req.vaultId or settings.default_vault_id,
                vote=req.vote,
                comment=req.comment,
                citation_correct=req.citationCorrect,
            )
        )

    publish(
        T.FEEDBACK_CREATED,
        {
            "event_id": new_id("evt"),
            "schema_version": SCHEMA_VERSION,
            "feedback_id": feedback_id,
            "query_id": req.queryId,
            "answer_id": req.answerId,
            "vote": req.vote,
            "comment": req.comment,
            "citation_correct": req.citationCorrect,
            "created_at": now_iso(),
        },
        key=req.queryId,
    )

    correction = None
    if req.vote == "down" and req.queryId:
        correction = _handle_correction(req.queryId, req.comment or "")

    return {"status": "ok", "feedbackId": feedback_id, "correctionCandidate": correction}
