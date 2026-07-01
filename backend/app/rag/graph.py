"""Graph expansion over Obsidian wikilinks/backlinks (EPIC-06).

Uses the edge index to pull chunks from notes linked to the top retrieval hits,
and applies configurable link/tag/folder boosts. All expansion parameters are
surfaced in the returned ``graph`` metadata for the retrieval debug panel.
"""
import logging

from ..config import settings
from ..es.client import get_es
from ..es.indexer import get_note, resolve_note_id_by_title
from ..es.indices import read_alias

log = logging.getLogger("rag.graph")


def get_outgoing_note_ids(vault_id: str, note_id: str) -> list[str]:
    """Resolve outgoing links at query time so it is independent of the order
    in which notes were indexed (edges always carry target_title)."""
    res = get_es().search(
        index=read_alias("edges"),
        size=100,
        query={"bool": {"must": [{"term": {"vault_id": vault_id}}, {"term": {"source_note_id": note_id}}]}},
    )
    ids: set[str] = set()
    for h in res["hits"]["hits"]:
        src = h["_source"]
        target = src.get("target_note_id") or resolve_note_id_by_title(vault_id, src.get("target_title"))
        if target:
            ids.add(target)
    ids.discard(note_id)
    return list(ids)


def get_backlink_note_ids(vault_id: str, note_id: str) -> list[str]:
    """Backlinks by target_note_id OR target_title, so unresolved edges still
    resolve to backlinks once the target note exists."""
    note = get_note(note_id)
    should: list[dict] = [{"term": {"target_note_id": note_id}}]
    if note and note.get("title"):
        should.append({"term": {"target_title.kw": note["title"]}})
    res = get_es().search(
        index=read_alias("edges"),
        size=100,
        query={"bool": {"must": [{"term": {"vault_id": vault_id}}], "should": should, "minimum_should_match": 1}},
    )
    ids = {h["_source"]["source_note_id"] for h in res["hits"]["hits"] if h["_source"].get("source_note_id")}
    ids.discard(note_id)
    return list(ids)


def get_note_chunks(vault_id: str, note_id: str, limit: int) -> list[dict]:
    res = get_es().search(
        index=read_alias("chunks"),
        size=limit,
        query={"bool": {"must": [{"term": {"note_id": note_id}}, {"term": {"deleted": False}}]}},
        sort=[{"chunk_index": "asc"}],
    )
    return [h["_source"] for h in res["hits"]["hits"]]


def _params() -> dict:
    return {
        "graph_depth": settings.graph_depth,
        "linked_note_chunk_limit": settings.linked_note_chunk_limit,
        "outgoing_link_boost": settings.outgoing_link_boost,
        "incoming_link_boost": settings.incoming_link_boost,
        "same_folder_boost": settings.same_folder_boost,
        "same_tag_boost": settings.same_tag_boost,
    }


def _folder(path: str | None) -> str:
    return (path or "").split("/")[0]


def expand_retrieval(vault_id: str, retr: dict, top_k: int | None = None) -> dict:
    top_k = top_k or settings.default_top_k
    base = retr.get("results", [])
    retr["mode"] = "HYBRID+GRAPH"
    if not base:
        retr["graph"] = {"added": 0, "params": _params()}
        return retr

    max_score = max((r["score"] for r in base), default=1.0) or 1.0
    top = base[0]
    top_tags = set(top.get("tags") or [])
    top_folder = _folder(top.get("path"))

    combined: dict[str, dict] = {}
    parent_norm: dict[str, float] = {}
    for r in base:
        norm = r["score"] / max_score
        parent_norm[r["note_id"]] = max(parent_norm.get(r["note_id"], 0.0), norm)
        boost = 0.0
        if top_tags & set(r.get("tags") or []):
            boost += settings.same_tag_boost
        if _folder(r.get("path")) == top_folder:
            boost += settings.same_folder_boost
        item = dict(r)
        item["fromGraph"] = False
        item["graphRelation"] = None
        item["graphScore"] = round(norm + boost, 6)
        combined[r["chunk_id"]] = item

    existing_notes = {r["note_id"] for r in base}
    seed_notes = list(dict.fromkeys(r["note_id"] for r in base[: max(1, top_k // 2)]))

    for seed in seed_notes:
        linked = [(n, "outgoing", settings.outgoing_link_boost) for n in get_outgoing_note_ids(vault_id, seed)]
        linked += [(n, "incoming", settings.incoming_link_boost) for n in get_backlink_note_ids(vault_id, seed)]
        for target_id, relation, rel_boost in linked:
            if not target_id or target_id in existing_notes:
                continue
            for c in get_note_chunks(vault_id, target_id, settings.linked_note_chunk_limit):
                cid = c["chunk_id"]
                if cid in combined:
                    continue
                score = round(parent_norm.get(seed, 0.5) * rel_boost, 6)
                combined[cid] = {
                    "chunk_id": cid,
                    "note_id": c.get("note_id"),
                    "note_title": c.get("title"),
                    "path": c.get("path"),
                    "heading_path": c.get("heading_path"),
                    "content": c.get("content"),
                    "source_type": c.get("source_type"),
                    "tags": c.get("tags", []),
                    "outgoing_links": c.get("outgoing_links", []),
                    "chunk_index": c.get("chunk_index"),
                    "bm25_score": None,
                    "vector_score": None,
                    "score": score,
                    "graphScore": score,
                    "fromGraph": True,
                    "graphRelation": relation,
                }

    ranked = sorted(combined.values(), key=lambda d: d["graphScore"], reverse=True)
    added = sum(1 for d in ranked if d.get("fromGraph"))
    limit = top_k + settings.linked_note_chunk_limit * 2
    retr["results"] = ranked[:limit]
    retr["graph"] = {"added": added, "params": _params(), "seedNotes": seed_notes}
    return retr
