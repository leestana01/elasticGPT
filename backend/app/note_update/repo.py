from datetime import datetime, timezone

from ..db.database import session_scope
from ..db.models import NoteUpdateCandidate
from ..events.ids import new_id


def _to_dict(c: NoteUpdateCandidate) -> dict:
    return {
        "candidateId": c.candidate_id,
        "queryId": c.query_id,
        "answerId": c.answer_id,
        "vaultId": c.vault_id,
        "userId": c.user_id,
        "candidateType": c.candidate_type,
        "targetNotePath": c.target_note_path,
        "targetHeading": c.target_heading,
        "markdownPatch": c.markdown_patch,
        "summary": c.summary,
        "sourceQuestion": c.source_question,
        "sourceAnswer": c.source_answer,
        "citations": c.citations or [],
        "relatedNotes": c.related_notes or [],
        "status": c.status,
        "patchHash": c.patch_hash,
        "origin": c.origin,
        "createdAt": c.created_at.isoformat() if c.created_at else None,
        "decidedAt": c.decided_at.isoformat() if c.decided_at else None,
    }


def create_candidate(data: dict) -> dict | None:
    """Create a PENDING candidate, deduplicating on (query_id, path, patch_hash)."""
    with session_scope() as session:
        dup = (
            session.query(NoteUpdateCandidate)
            .filter(
                NoteUpdateCandidate.query_id == data.get("query_id"),
                NoteUpdateCandidate.target_note_path == data["target_note_path"],
                NoteUpdateCandidate.patch_hash == data["patch_hash"],
            )
            .first()
        )
        if dup is not None:
            return None
        candidate = NoteUpdateCandidate(candidate_id=new_id("cand"), status="PENDING", **data)
        session.add(candidate)
        session.flush()
        return _to_dict(candidate)


def list_candidates(status: str | None = None, vault_id: str | None = None) -> list[dict]:
    with session_scope() as session:
        q = session.query(NoteUpdateCandidate)
        if status:
            q = q.filter(NoteUpdateCandidate.status == status)
        if vault_id:
            q = q.filter(NoteUpdateCandidate.vault_id == vault_id)
        return [_to_dict(c) for c in q.order_by(NoteUpdateCandidate.created_at.desc()).all()]


def get_candidate(candidate_id: str) -> dict | None:
    with session_scope() as session:
        c = session.get(NoteUpdateCandidate, candidate_id)
        return _to_dict(c) if c else None


def decide(candidate_id: str, new_status: str, from_status: str = "PENDING") -> dict | None:
    """Transition status guarding against double decisions. Returns dict or None
    if the candidate is missing or not in the expected state."""
    with session_scope() as session:
        c = session.get(NoteUpdateCandidate, candidate_id)
        if c is None or c.status != from_status:
            return None
        c.status = new_status
        c.decided_at = datetime.now(timezone.utc)
        session.flush()
        return _to_dict(c)


def mark_applied(candidate_id: str) -> dict | None:
    with session_scope() as session:
        c = session.get(NoteUpdateCandidate, candidate_id)
        if c is None or c.status == "APPLIED":
            return None
        c.status = "APPLIED"
        session.flush()
        return _to_dict(c)


def reject_pending_for_query(query_id: str) -> int:
    with session_scope() as session:
        rows = (
            session.query(NoteUpdateCandidate)
            .filter(NoteUpdateCandidate.query_id == query_id, NoteUpdateCandidate.status == "PENDING")
            .all()
        )
        for c in rows:
            c.status = "REJECTED"
            c.decided_at = datetime.now(timezone.utc)
        return len(rows)
