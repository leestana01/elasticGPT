from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func

from ..config import settings
from ..db.database import session_scope
from ..db.models import NoteUpdateCandidate, QueryLog
from ..ops.dlq import count_dlq, list_dlq, reprocess
from ..ops.metrics import counters, recent_events
from ..ops.reindex import create_job, get_job, list_jobs

router = APIRouter(tags=["ops"])


class ReindexRequest(BaseModel):
    vaultId: str | None = None
    path: str | None = None
    reason: str | None = None


@router.get("/api/dlq")
def api_dlq(status: str | None = None) -> dict:
    return {"events": list_dlq(status)}


@router.post("/api/dlq/{dlq_id}/reprocess")
def api_dlq_reprocess(dlq_id: str) -> dict:
    d = reprocess(dlq_id)
    if d is None:
        raise HTTPException(status_code=409, detail="already reprocessed or not found")
    return {"status": "REPROCESSED", "event": d}


@router.post("/api/reindex")
def api_reindex(req: ReindexRequest) -> dict:
    vault_id = req.vaultId or settings.default_vault_id
    return {"job": create_job(vault_id, req.path, req.reason)}


@router.get("/api/reindex")
def api_reindex_list(vaultId: str | None = None) -> dict:
    return {"jobs": list_jobs(vaultId)}


@router.get("/api/reindex/{job_id}")
def api_reindex_get(job_id: str) -> dict:
    j = get_job(job_id)
    if not j:
        raise HTTPException(status_code=404, detail="reindex job not found")
    return {"job": j}


@router.get("/api/indexing/status")
def api_indexing_status(limit: int = 50) -> dict:
    return {"events": recent_events(limit), "reindexJobs": list_jobs(limit=10)}


@router.get("/api/metrics")
def api_metrics() -> dict:
    with session_scope() as session:
        q_count = session.query(func.count(QueryLog.query_id)).scalar() or 0
        avg_latency = session.query(func.avg(QueryLog.latency_ms)).scalar() or 0
        tokens = (
            session.query(func.coalesce(func.sum(QueryLog.prompt_tokens + QueryLog.completion_tokens), 0)).scalar()
            or 0
        )
        candidates = dict(
            session.query(NoteUpdateCandidate.status, func.count()).group_by(NoteUpdateCandidate.status).all()
        )
    return {
        "pipeline": counters(),
        "queries": {"count": int(q_count), "avgLatencyMs": round(float(avg_latency), 1), "totalTokens": int(tokens)},
        "candidates": candidates,
        "dlqCount": count_dlq(None),
        "dlqNew": count_dlq("NEW"),
    }
