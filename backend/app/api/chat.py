import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import settings
from ..db.database import session_scope
from ..db.models import QueryLog
from ..events.ids import new_id, now_iso
from ..events.schemas import SCHEMA_VERSION
from ..kafka import topics as T
from ..kafka.producer import publish
from ..rag.context import build_context
from ..rag.generation import generate_answer
from ..rag.retrieval import hybrid_retrieve

router = APIRouter(prefix="/api/rag", tags=["rag"])
log = logging.getLogger("api.chat")


class SearchOptions(BaseModel):
    topK: int | None = None
    graphExpansion: bool | None = None


class ChatRequest(BaseModel):
    message: str
    vaultId: str | None = None
    userId: str | None = None
    searchOptions: SearchOptions | None = None


def _save_log(**kwargs) -> None:
    try:
        with session_scope() as session:
            session.add(QueryLog(**kwargs))
    except Exception:  # noqa: BLE001
        log.exception("failed to persist query log")


def _publish_answer(query_id, answer_id, vault_id, question, gen, retr) -> None:
    try:
        publish(
            T.ANSWER_GENERATED,
            {
                "event_id": new_id("evt"),
                "schema_version": SCHEMA_VERSION,
                "query_id": query_id,
                "answer_id": answer_id,
                "vault_id": vault_id,
                "question": question,
                "answer": gen["answer"],
                "citations": gen["citations"],
                "retrieval_chunk_ids": [r["chunk_id"] for r in retr["results"]],
                "insufficient_context": gen["insufficientContext"],
                "created_at": now_iso(),
            },
            key=query_id,
        )
    except Exception:  # noqa: BLE001
        log.exception("failed to publish rag.answer.generated")


@router.post("/chat")
def chat(req: ChatRequest) -> dict:
    vault_id = req.vaultId or settings.default_vault_id
    query_id = new_id("qry")
    answer_id = new_id("ans")
    top_k = (req.searchOptions.topK if req.searchOptions and req.searchOptions.topK else settings.default_top_k)
    graph = bool(req.searchOptions and req.searchOptions.graphExpansion)

    try:
        retr = hybrid_retrieve(vault_id, req.message, top_k=top_k, user_id=req.userId)
        if graph:
            try:
                from ..rag.graph import expand_retrieval

                retr = expand_retrieval(vault_id, retr, top_k=top_k)
            except ImportError:
                pass
        ctx = build_context(retr["results"])
        gen = generate_answer(req.message, ctx)
    except Exception as e:  # noqa: BLE001
        log.exception("chat failed")
        _save_log(
            query_id=query_id, answer_id=answer_id, vault_id=vault_id, user_id=req.userId,
            question=req.message, error_type=type(e).__name__, error_message=str(e),
        )
        raise HTTPException(status_code=500, detail=f"answer generation failed: {e}")

    _save_log(
        query_id=query_id, answer_id=answer_id, vault_id=vault_id, user_id=req.userId,
        question=req.message,
        retrieval_chunk_ids=[r["chunk_id"] for r in retr["results"]],
        retrieval_scores=[r["score"] for r in retr["results"]],
        context_meta={
            "insufficient": ctx["insufficient"],
            "total_tokens": ctx["total_tokens"],
            "block_count": len(ctx["blocks"]),
        },
        answer=gen["answer"], citations=gen["citations"],
        prompt_tokens=gen["usage"]["promptTokens"], completion_tokens=gen["usage"]["completionTokens"],
        latency_ms=gen["latencyMs"],
    )
    _publish_answer(query_id, answer_id, vault_id, req.message, gen, retr)

    return {
        "queryId": query_id,
        "answerId": answer_id,
        "answer": gen["answer"],
        "citations": gen["citations"],
        "retrieval": {
            "mode": retr["mode"],
            "topK": retr["top_k"],
            "candidateCount": retr["candidate_count"],
            "graphExpansion": graph,
        },
        "usage": gen["usage"],
        "latencyMs": gen["latencyMs"],
        "insufficientContext": gen["insufficientContext"],
    }
