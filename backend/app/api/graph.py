from fastapi import APIRouter

from ..config import settings
from ..es.indexer import get_note
from ..rag.graph import get_backlink_note_ids, get_note_chunks, get_outgoing_note_ids

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("/backlinks")
def backlinks(noteId: str, vaultId: str | None = None) -> dict:
    vault_id = vaultId or settings.default_vault_id
    notes = []
    for nid in get_backlink_note_ids(vault_id, noteId):
        note = get_note(nid)
        chunks = get_note_chunks(vault_id, nid, 1)
        notes.append(
            {
                "noteId": nid,
                "title": note.get("title") if note else None,
                "path": note.get("path") if note else None,
                "representativeChunk": chunks[0]["content"] if chunks else None,
            }
        )
    return {"noteId": noteId, "backlinks": notes, "count": len(notes)}


@router.get("/links")
def links(noteId: str, vaultId: str | None = None) -> dict:
    vault_id = vaultId or settings.default_vault_id
    return {
        "noteId": noteId,
        "outgoing": get_outgoing_note_ids(vault_id, noteId),
        "backlinks": get_backlink_note_ids(vault_id, noteId),
    }
