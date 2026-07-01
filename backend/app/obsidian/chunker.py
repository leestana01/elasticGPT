import hashlib
import re

from ..config import settings


def estimate_tokens(text: str) -> int:
    """Rough token estimate that works for mixed Korean/English text."""
    return max(1, round(len(text) / 3.5))


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _overlap_tail(paras: list[str]) -> tuple[list[str], int]:
    """Keep trailing paragraphs up to the configured overlap budget."""
    tail: list[str] = []
    tokens = 0
    for p in reversed(paras):
        pt = estimate_tokens(p)
        if tokens + pt > settings.chunk_overlap_tokens and tail:
            break
        tail.insert(0, p)
        tokens += pt
    return tail, tokens


def _pieces(text: str) -> list[str]:
    if estimate_tokens(text) <= settings.chunk_max_tokens:
        return [text]
    pieces: list[str] = []
    cur: list[str] = []
    cur_tokens = 0
    for p in _paragraphs(text):
        pt = estimate_tokens(p)
        if cur and cur_tokens + pt > settings.chunk_max_tokens:
            pieces.append("\n\n".join(cur))
            cur, cur_tokens = _overlap_tail(cur)
        cur.append(p)
        cur_tokens += pt
    if cur:
        pieces.append("\n\n".join(cur))
    return pieces


def _sha(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_note(sections: list[dict], ctx: dict) -> list[dict]:
    """Split a parsed note into retrievable chunks.

    ctx must provide: vault_id, path, title, note_version. Chunk ids are
    deterministic so re-processing the same note version overwrites in place.
    """
    chunks: list[dict] = []
    idx = 0
    for section in sections:
        heading_path = section.get("heading_path", ctx["title"])
        for piece in _pieces(section.get("text", "")):
            content = f"{heading_path}\n{piece}".strip()
            content_for_embedding = f"{ctx['title']}\n{heading_path}\n{piece}".strip()
            chunk_id = f"{ctx['vault_id']}:{ctx['path']}:v{ctx['note_version']}:c{idx:03d}"
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "chunk_index": idx,
                    "heading_path": heading_path,
                    "content": content,
                    "content_for_embedding": content_for_embedding,
                    "chunk_hash": _sha(content),
                }
            )
            idx += 1
    return chunks
