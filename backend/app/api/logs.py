from fastapi import APIRouter, HTTPException

from ..rag.query_logs import get_query_log, list_query_logs

router = APIRouter(prefix="/api/query-logs", tags=["logs"])


@router.get("")
def api_list(limit: int = 20, vaultId: str | None = None) -> dict:
    return {"logs": list_query_logs(limit=limit, vault_id=vaultId)}


@router.get("/{query_id}")
def api_get(query_id: str) -> dict:
    q = get_query_log(query_id)
    if not q:
        raise HTTPException(status_code=404, detail="query log not found")
    return {"log": q}
