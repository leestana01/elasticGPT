from ..db.database import session_scope
from ..db.models import QueryLog


def _to_dict(q: QueryLog) -> dict:
    return {
        "query_id": q.query_id,
        "answer_id": q.answer_id,
        "vault_id": q.vault_id,
        "user_id": q.user_id,
        "question": q.question,
        "retrieval_chunk_ids": q.retrieval_chunk_ids or [],
        "retrieval_scores": q.retrieval_scores or [],
        "context_meta": q.context_meta or {},
        "answer": q.answer,
        "citations": q.citations or [],
        "prompt_tokens": q.prompt_tokens,
        "completion_tokens": q.completion_tokens,
        "latency_ms": q.latency_ms,
        "error_type": q.error_type,
        "error_message": q.error_message,
        "created_at": q.created_at.isoformat() if q.created_at else None,
    }


def get_query_log(query_id: str) -> dict | None:
    with session_scope() as session:
        q = session.get(QueryLog, query_id)
        return _to_dict(q) if q else None


def list_query_logs(limit: int = 20, vault_id: str | None = None) -> list[dict]:
    with session_scope() as session:
        q = session.query(QueryLog)
        if vault_id:
            q = q.filter(QueryLog.vault_id == vault_id)
        return [_to_dict(x) for x in q.order_by(QueryLog.created_at.desc()).limit(limit).all()]
