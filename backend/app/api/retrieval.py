from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import settings
from ..es.client import get_es
from ..es.indices import read_alias
from ..rag.context import build_context
from ..rag.retrieval import hybrid_retrieve

router = APIRouter(prefix="/api/retrieval", tags=["retrieval"])


class RetrievalRequest(BaseModel):
    query: str
    vaultId: str | None = None
    userId: str | None = None
    topK: int | None = None
    graphExpansion: bool | None = None


@router.post("/debug")
def retrieval_debug(req: RetrievalRequest) -> dict:
    """Return raw candidates + which chunks were selected into the context.

    Backs the Retrieval Debug Panel (EPIC-08).
    """
    vault_id = req.vaultId or settings.default_vault_id
    top_k = req.topK or settings.default_top_k
    retr = hybrid_retrieve(vault_id, req.query, top_k=top_k, user_id=req.userId)

    graph_added: set[str] = set()
    if req.graphExpansion:
        try:
            from ..rag.graph import expand_retrieval

            base_ids = {r["chunk_id"] for r in retr["results"]}
            retr = expand_retrieval(vault_id, retr, top_k=top_k)
            graph_added = {r["chunk_id"] for r in retr["results"]} - base_ids
        except ImportError:
            pass

    ctx = build_context(retr["results"])
    context_ids: set[str] = set()
    for b in ctx["blocks"]:
        context_ids.update(b.get("merged_chunk_ids", [b["chunk_id"]]))

    for r in retr["results"]:
        r["inContext"] = r["chunk_id"] in context_ids
        r["fromGraph"] = r["chunk_id"] in graph_added

    return {
        "results": retr["results"],
        "contextBlocks": ctx["blocks"],
        "droppedChunkIds": ctx["dropped_chunk_ids"],
        "candidateCount": retr["candidate_count"],
        "mode": retr["mode"],
    }


@router.get("/chunk")
def get_chunk(chunkId: str) -> dict:
    """Full chunk content for the citation preview (US-08-03).

    chunk_id is passed as a query param because it contains '/' which does not
    survive a path parameter cleanly.
    """
    try:
        res = get_es().get(index=read_alias("chunks"), id=chunkId)
    except Exception:
        raise HTTPException(status_code=404, detail="chunk not found")
    s = res["_source"]
    return {
        "chunkId": chunkId,
        "noteTitle": s.get("title"),
        "path": s.get("path"),
        "headingPath": s.get("heading_path"),
        "content": s.get("content"),
        "sourceType": s.get("source_type"),
    }
