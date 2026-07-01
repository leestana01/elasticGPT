from ..config import settings
from ..obsidian.chunker import estimate_tokens


def _citation(r: dict) -> dict:
    return {
        "chunk_id": r["chunk_id"],
        "note_id": r.get("note_id"),
        "note_title": r.get("note_title"),
        "path": r.get("path"),
        "heading_path": r.get("heading_path"),
        "content": r.get("content"),
        "source_type": r.get("source_type"),
        "chunk_index": r.get("chunk_index"),
        "score": r.get("score"),
    }


def _merge_adjacent(blocks: list[dict]) -> list[dict]:
    """Merge consecutive chunks of the same note into a single context block."""
    merged: list[dict] = []
    for b in blocks:
        prev = merged[-1] if merged else None
        if (
            prev
            and prev["note_id"] == b["note_id"]
            and isinstance(prev.get("chunk_index"), int)
            and isinstance(b.get("chunk_index"), int)
            and b["chunk_index"] == prev["chunk_index"] + 1
        ):
            prev["content"] = prev["content"] + "\n\n" + b["content"]
            prev["chunk_index"] = b["chunk_index"]
            prev["merged_chunk_ids"] = prev.get("merged_chunk_ids", [prev["chunk_id"]]) + [b["chunk_id"]]
        else:
            merged.append(dict(b))
    return merged


def build_context(results: list[dict], token_limit: int | None = None) -> dict:
    """Deduplicate, cap to the token budget, and merge adjacent chunks.

    Returns blocks (with citation metadata), an insufficient flag and dropped
    chunk ids (used by the retrieval debug panel).
    """
    token_limit = token_limit or settings.context_token_limit
    selected: list[dict] = []
    dropped: list[str] = []
    seen: set[str] = set()
    total = 0
    for r in results:
        cid = r["chunk_id"]
        if cid in seen:
            continue
        seen.add(cid)
        tokens = estimate_tokens(r.get("content", ""))
        if selected and total + tokens > token_limit:
            dropped.append(cid)
            continue
        selected.append(_citation(r))
        total += tokens

    blocks = _merge_adjacent(selected)
    return {
        "blocks": blocks,
        "insufficient": len(blocks) == 0,
        "total_tokens": total,
        "dropped_chunk_ids": dropped,
    }
