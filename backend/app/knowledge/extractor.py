import hashlib
import re

from ..db.database import session_scope
from ..db.models import Feedback
from ..note_update.markdown import (
    APPEND_HEADING,
    build_append_block,
    build_new_note,
    slugify,
)

_INSUFFICIENT_MARKERS = ("근거를 찾지 못", "답변을 보류")


def _summary(answer: str) -> str:
    parts = [p for p in re.split(r"(?<=[.!?。])\s+|\n+", answer.strip()) if p.strip()]
    return " ".join(parts[:2])[:400]


def _patch_hash(target_path: str, patch: str) -> str:
    return "sha256:" + hashlib.sha256((target_path + patch).encode("utf-8")).hexdigest()


def has_negative_feedback(query_id: str | None, answer_id: str | None) -> bool:
    if not query_id and not answer_id:
        return False
    with session_scope() as session:
        q = session.query(Feedback).filter(Feedback.vote == "down")
        q = q.filter((Feedback.query_id == query_id) | (Feedback.answer_id == answer_id))
        return q.first() is not None


def _build(candidate_type, target_path, target_heading, patch, *, event, summary, related, origin):
    return {
        "query_id": event.get("query_id"),
        "answer_id": event.get("answer_id"),
        "vault_id": event.get("vault_id"),
        "user_id": event.get("user_id"),
        "candidate_type": candidate_type,
        "target_note_path": target_path,
        "target_heading": target_heading,
        "markdown_patch": patch,
        "summary": summary,
        "source_question": event.get("question", ""),
        "source_answer": event.get("answer", ""),
        "citations": event.get("citations") or [],
        "related_notes": related,
        "patch_hash": _patch_hash(target_path, patch),
        "origin": origin,
    }


def _choose_target(citations, question, summary, answer, related, event, origin):
    top = citations[0] if citations else None
    if top and top.get("path") and top.get("sourceType") != "generated":
        patch = build_append_block(question, summary, citations)
        return _build("APPEND", top["path"], APPEND_HEADING, patch,
                      event=event, summary=summary, related=related, origin=origin)
    target_path = f"90_Generated/QA - {slugify(question)}.md"
    patch = build_new_note(question, summary, answer, citations, related)
    return _build("NEW", target_path, None, patch,
                  event=event, summary=summary, related=related, origin=origin)


def extract(event: dict) -> dict | None:
    """Turn a rag.answer.generated event into a note-update candidate, or None if
    the exchange is not worth saving (US-07-02)."""
    question = (event.get("question") or "").strip()
    answer = (event.get("answer") or "").strip()
    citations = event.get("citations") or []

    if event.get("insufficient_context"):
        return None
    if len(question) < 6 or not answer:
        return None
    if any(m in answer for m in _INSUFFICIENT_MARKERS):
        return None
    if not citations:
        return None
    if has_negative_feedback(event.get("query_id"), event.get("answer_id")):
        return None

    summary = _summary(answer)
    related = list(dict.fromkeys(c.get("noteTitle") for c in citations if c.get("noteTitle")))
    return _choose_target(citations, question, summary, answer, related, event, "knowledge")


def build_correction(query_log: dict, comment: str) -> dict:
    """Build a correction candidate from a user's correction comment (US-07-07)."""
    citations = query_log.get("citations") or []
    question = query_log.get("question", "")
    related = list(dict.fromkeys(c.get("noteTitle") for c in citations if c.get("noteTitle")))
    event = {
        "query_id": query_log.get("query_id"),
        "answer_id": query_log.get("answer_id"),
        "vault_id": query_log.get("vault_id"),
        "user_id": query_log.get("user_id"),
        "question": question,
        "answer": f"(사용자 정정) {comment}",
        "citations": citations,
    }
    return _choose_target(citations, question, comment.strip()[:400], event["answer"], related, event, "correction")
