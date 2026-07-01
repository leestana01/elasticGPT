"""Elasticsearch index mappings, versioning and alias strategy.

Each logical index maps to a versioned physical index (``..._v1``) plus two
aliases:

* read alias  = ``rag_obsidian_chunks``        (queries read through this)
* write alias = ``rag_obsidian_chunks_write``   (indexing writes through this)

A mapping change is rolled out by creating ``..._v2``, reindexing into it and
atomically swapping both aliases (see :func:`switch_version`). Because reads and
writes go through aliases, the old version keeps serving queries until the swap,
so search never breaks mid-reindex (US-04-05).
"""
import logging

from ..config import settings
from .client import get_es

log = logging.getLogger("es.indices")


def _text_kw() -> dict:
    return {"type": "text", "fields": {"kw": {"type": "keyword"}}}


def _chunk_mappings() -> dict:
    return {
        "properties": {
            "chunk_id": {"type": "keyword"},
            "note_id": {"type": "keyword"},
            "vault_id": {"type": "keyword"},
            "user_id": {"type": "keyword"},
            "path": {"type": "keyword"},
            "folder": {"type": "keyword"},
            "title": _text_kw(),
            "heading_path": {"type": "text"},
            "tags": {"type": "keyword"},
            "outgoing_links": {"type": "keyword"},
            "content": {"type": "text"},
            "content_vector": {
                "type": "dense_vector",
                "dims": settings.embedding_dim,
                "index": True,
                "similarity": "cosine",
            },
            "source_type": {"type": "keyword"},  # original | generated
            "chunk_index": {"type": "integer"},
            "note_version": {"type": "integer"},
            "content_hash": {"type": "keyword"},
            "embedding_model": {"type": "keyword"},
            "deleted": {"type": "boolean"},
            "created_at": {"type": "date"},
        }
    }


def _note_mappings() -> dict:
    return {
        "properties": {
            "note_id": {"type": "keyword"},
            "vault_id": {"type": "keyword"},
            "user_id": {"type": "keyword"},
            "path": {"type": "keyword"},
            "title": _text_kw(),
            "folder": {"type": "keyword"},
            "frontmatter": {"type": "object", "enabled": True},
            "tags": {"type": "keyword"},
            "outgoing_links": {"type": "keyword"},
            "incoming_links": {"type": "keyword"},
            "note_version": {"type": "integer"},
            "content_hash": {"type": "keyword"},
            "chunk_count": {"type": "integer"},
            "source_type": {"type": "keyword"},
            "deleted": {"type": "boolean"},
            "updated_at": {"type": "date"},
        }
    }


def _edge_mappings() -> dict:
    return {
        "properties": {
            "edge_id": {"type": "keyword"},
            "vault_id": {"type": "keyword"},
            "source_note_id": {"type": "keyword"},
            "target_note_id": {"type": "keyword"},
            "source_title": _text_kw(),
            "target_title": _text_kw(),
            "link_type": {"type": "keyword"},  # wikilink
            "resolved": {"type": "boolean"},
        }
    }


def _qa_mappings() -> dict:
    return {
        "properties": {
            "candidate_id": {"type": "keyword"},
            "query_id": {"type": "keyword"},
            "answer_id": {"type": "keyword"},
            "vault_id": {"type": "keyword"},
            "summary": {"type": "text"},
            "source_question": {"type": "text"},
            "source_answer": {"type": "text"},
            "related_notes": {"type": "keyword"},
            "citations": {"type": "object", "enabled": True},
            "status": {"type": "keyword"},
            "target_note_path": {"type": "keyword"},
            "markdown_patch": {"type": "text"},
            "created_at": {"type": "date"},
        }
    }


# logical name -> (physical suffix, current version, mappings builder)
INDICES = {
    "chunks": ("obsidian_chunks", 1, _chunk_mappings),
    "notes": ("obsidian_notes", 1, _note_mappings),
    "edges": ("obsidian_edges", 1, _edge_mappings),
    "qa": ("qa_knowledge", 1, _qa_mappings),
}


def base_name(logical: str) -> str:
    return f"{settings.index_prefix}_{INDICES[logical][0]}"


def versioned_name(logical: str, version: int | None = None) -> str:
    version = version if version is not None else INDICES[logical][1]
    return f"{base_name(logical)}_v{version}"


def read_alias(logical: str) -> str:
    return base_name(logical)


def write_alias(logical: str) -> str:
    return f"{base_name(logical)}_write"


def create_version(logical: str, version: int | None = None) -> str:
    es = get_es()
    idx = versioned_name(logical, version)
    if not es.indices.exists(index=idx):
        es.indices.create(
            index=idx,
            mappings=INDICES[logical][2](),
            settings={"number_of_shards": 1, "number_of_replicas": 0},
        )
        log.info("created index %s", idx)
    return idx


def switch_version(logical: str, version: int) -> None:
    """Atomically point read+write aliases at a (new) version."""
    es = get_es()
    idx = versioned_name(logical, version)
    actions = []
    for alias in (read_alias(logical), write_alias(logical)):
        if es.indices.exists_alias(name=alias):
            actions.append({"remove": {"index": "*", "alias": alias}})
        actions.append({"add": {"index": idx, "alias": alias}})
    es.indices.update_aliases(actions=actions)
    log.info("aliases -> %s", idx)


def bootstrap_indices() -> None:
    """Create every versioned index and point aliases at it if missing."""
    es = get_es()
    for logical in INDICES:
        idx = create_version(logical)
        for alias in (read_alias(logical), write_alias(logical)):
            if not es.indices.exists_alias(name=alias):
                es.indices.put_alias(index=idx, name=alias)
                log.info("alias %s -> %s", alias, idx)
