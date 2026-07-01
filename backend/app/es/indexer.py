import logging

from ..events.ids import now_iso
from .client import get_es
from .indices import read_alias, write_alias

log = logging.getLogger("es.indexer")


def index_qa_knowledge(candidate: dict) -> None:
    es = get_es()
    es.index(
        index=write_alias("qa"),
        id=candidate["candidateId"],
        document={
            "candidate_id": candidate["candidateId"],
            "query_id": candidate.get("queryId"),
            "answer_id": candidate.get("answerId"),
            "vault_id": candidate.get("vaultId"),
            "summary": candidate.get("summary"),
            "source_question": candidate.get("sourceQuestion"),
            "source_answer": candidate.get("sourceAnswer"),
            "related_notes": candidate.get("relatedNotes", []),
            "citations": candidate.get("citations", []),
            "status": candidate.get("status"),
            "target_note_path": candidate.get("targetNotePath"),
            "markdown_patch": candidate.get("markdownPatch"),
            "created_at": now_iso(),
        },
    )


def get_note(note_id: str) -> dict | None:
    es = get_es()
    try:
        res = es.get(index=read_alias("notes"), id=note_id)
        return res["_source"]
    except Exception:  # noqa: BLE001  (404 not found → None)
        return None


def resolve_note_id_by_title(vault_id: str, title: str | None) -> str | None:
    if not title:
        return None
    es = get_es()
    try:
        res = es.search(
            index=read_alias("notes"),
            size=1,
            query={"bool": {"must": [{"term": {"vault_id": vault_id}}, {"term": {"title.kw": title}}]}},
        )
        hits = res["hits"]["hits"]
        return hits[0]["_source"]["note_id"] if hits else None
    except Exception:  # noqa: BLE001
        return None


def index_chunks(chunks: list[dict], note_meta: dict) -> list[str]:
    es = get_es()
    ids = []
    for c in chunks:
        doc = {
            "chunk_id": c["chunk_id"],
            "note_id": note_meta["note_id"],
            "vault_id": note_meta["vault_id"],
            "user_id": note_meta.get("user_id"),
            "path": note_meta["path"],
            "folder": note_meta["folder"],
            "title": note_meta["title"],
            "heading_path": c["heading_path"],
            "tags": note_meta.get("tags", []),
            "outgoing_links": note_meta.get("outgoing_links", []),
            "content": c["content"],
            "content_vector": c["content_vector"],
            "source_type": note_meta.get("source_type", "original"),
            "chunk_index": c["chunk_index"],
            "note_version": note_meta["note_version"],
            "content_hash": c["chunk_hash"],
            "embedding_model": c.get("embedding_model"),
            "deleted": False,
            "created_at": now_iso(),
        }
        es.index(index=write_alias("chunks"), id=c["chunk_id"], document=doc)
        ids.append(c["chunk_id"])
    return ids


def index_note(note_meta: dict, chunk_count: int) -> None:
    es = get_es()
    doc = {
        "note_id": note_meta["note_id"],
        "vault_id": note_meta["vault_id"],
        "user_id": note_meta.get("user_id"),
        "path": note_meta["path"],
        "title": note_meta["title"],
        "folder": note_meta["folder"],
        "frontmatter": note_meta.get("frontmatter", {}),
        "tags": note_meta.get("tags", []),
        "outgoing_links": note_meta.get("outgoing_links", []),
        "note_version": note_meta["note_version"],
        "content_hash": note_meta["content_hash"],
        "chunk_count": chunk_count,
        "source_type": note_meta.get("source_type", "original"),
        "deleted": False,
        "updated_at": now_iso(),
    }
    es.index(index=write_alias("notes"), id=note_meta["note_id"], document=doc)


def index_edges(note_meta: dict) -> None:
    es = get_es()
    vault_id = note_meta["vault_id"]
    source_id = note_meta["note_id"]
    # drop this note's previous edges so removed links / renames don't linger
    es.delete_by_query(
        index=write_alias("edges"),
        query={"term": {"source_note_id": source_id}},
        refresh=True,
        conflicts="proceed",
    )
    for target_title in note_meta.get("outgoing_links", []):
        target_id = resolve_note_id_by_title(vault_id, target_title)
        edge_id = f"{source_id}->{target_title}"
        es.index(
            index=write_alias("edges"),
            id=edge_id,
            document={
                "edge_id": edge_id,
                "vault_id": vault_id,
                "source_note_id": source_id,
                "target_note_id": target_id,
                "source_title": note_meta["title"],
                "target_title": target_title,
                "link_type": "wikilink",
                "resolved": target_id is not None,
            },
        )


def resolve_incoming_edges(note_meta: dict) -> None:
    """Back-fill edges that pointed at this note by title but were unresolved
    because the target note was not yet indexed (order-independent graph)."""
    es = get_es()
    es.update_by_query(
        index=write_alias("edges"),
        query={
            "bool": {
                "must": [
                    {"term": {"vault_id": note_meta["vault_id"]}},
                    {"term": {"target_title.kw": note_meta["title"]}},
                    {"term": {"resolved": False}},
                ]
            }
        },
        script={
            "source": "ctx._source.target_note_id = params.nid; ctx._source.resolved = true",
            "params": {"nid": note_meta["note_id"]},
        },
        refresh=True,
        conflicts="proceed",
    )


def delete_stale_chunks(note_id: str, keep_version: int) -> None:
    """Remove chunks left over from previous versions of a note."""
    es = get_es()
    es.delete_by_query(
        index=write_alias("chunks"),
        query={
            "bool": {
                "must": [{"term": {"note_id": note_id}}],
                "must_not": [{"term": {"note_version": keep_version}}],
            }
        },
        refresh=True,
        conflicts="proceed",
    )


def soft_delete_note(note_id: str) -> None:
    """Mark a note and all its chunks deleted so retrieval excludes them."""
    es = get_es()
    es.update_by_query(
        index=write_alias("chunks"),
        query={"term": {"note_id": note_id}},
        script={"source": "ctx._source.deleted = true"},
        refresh=True,
        conflicts="proceed",
    )
    es.delete_by_query(
        index=write_alias("edges"),
        query={"term": {"source_note_id": note_id}},
        refresh=True,
        conflicts="proceed",
    )
    try:
        es.update(index=write_alias("notes"), id=note_id, doc={"deleted": True})
    except Exception:  # noqa: BLE001
        pass
