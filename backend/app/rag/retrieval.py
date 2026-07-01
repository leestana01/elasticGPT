import logging

from ..config import settings
from ..es.client import get_es
from ..es.indices import read_alias
from ..providers.factory import get_embedding_provider

log = logging.getLogger("rag.retrieval")

_SOURCE = [
    "chunk_id", "note_id", "title", "path", "heading_path", "content",
    "source_type", "tags", "outgoing_links", "chunk_index",
]


def _rrf(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, cid in enumerate(ranking):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
    return scores


def hybrid_retrieve(
    vault_id: str,
    query: str,
    top_k: int | None = None,
    user_id: str | None = None,
    pool: int | None = None,
) -> dict:
    """BM25 keyword + kNN vector search fused with reciprocal rank fusion.

    Applies vault_id / user_id / deleted=false filters (US-05-01).
    """
    top_k = top_k or settings.default_top_k
    pool = pool or settings.candidate_pool
    es = get_es()

    query_vector = get_embedding_provider().embed_one(query)

    filters: list[dict] = [{"term": {"vault_id": vault_id}}, {"term": {"deleted": False}}]
    if user_id:
        filters.append({"term": {"user_id": user_id}})

    keyword = es.search(
        index=read_alias("chunks"),
        size=pool,
        source=_SOURCE,
        query={
            "bool": {
                "must": [{"multi_match": {"query": query, "fields": ["title^2", "heading_path^1.5", "content"]}}],
                "filter": filters,
            }
        },
    )
    vector = es.search(
        index=read_alias("chunks"),
        size=pool,
        source=_SOURCE,
        knn={
            "field": "content_vector",
            "query_vector": query_vector,
            "k": pool,
            "num_candidates": pool * 4,
            "filter": {"bool": {"filter": filters}},
        },
    )

    docs: dict[str, dict] = {}
    kw_rank: list[str] = []
    vec_rank: list[str] = []
    for h in keyword["hits"]["hits"]:
        cid = h["_source"]["chunk_id"]
        docs.setdefault(cid, dict(h["_source"]))
        docs[cid]["_bm25"] = h["_score"]
        kw_rank.append(cid)
    for h in vector["hits"]["hits"]:
        cid = h["_source"]["chunk_id"]
        docs.setdefault(cid, dict(h["_source"]))
        docs[cid]["_vec"] = h["_score"]
        vec_rank.append(cid)

    rrf = _rrf([kw_rank, vec_rank])
    ranked = sorted(docs.values(), key=lambda d: rrf.get(d["chunk_id"], 0.0), reverse=True)

    results = []
    for d in ranked[:top_k]:
        results.append(
            {
                "chunk_id": d["chunk_id"],
                "note_id": d.get("note_id"),
                "note_title": d.get("title"),
                "path": d.get("path"),
                "heading_path": d.get("heading_path"),
                "content": d.get("content"),
                "source_type": d.get("source_type"),
                "tags": d.get("tags", []),
                "outgoing_links": d.get("outgoing_links", []),
                "chunk_index": d.get("chunk_index"),
                "bm25_score": d.get("_bm25"),
                "vector_score": d.get("_vec"),
                "score": round(rrf.get(d["chunk_id"], 0.0), 6),
            }
        )
    return {"results": results, "candidate_count": len(docs), "mode": "HYBRID", "top_k": top_k}
