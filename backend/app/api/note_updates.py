import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..events.ids import new_id, now_iso
from ..events.schemas import SCHEMA_VERSION
from ..kafka import topics as T
from ..kafka.producer import publish
from ..note_update.repo import decide, get_candidate, list_candidates

router = APIRouter(prefix="/api/note-updates", tags=["note-update"])
log = logging.getLogger("api.note_updates")


class DecisionRequest(BaseModel):
    decidedBy: str | None = None


def _publish(topic: str, candidate: dict) -> None:
    publish(
        topic,
        {"event_id": new_id("evt"), "schema_version": SCHEMA_VERSION, "created_at": now_iso(), **candidate},
        key=candidate["candidateId"],
    )


@router.get("")
def api_list(status: str | None = None, vaultId: str | None = None) -> dict:
    return {"candidates": list_candidates(status=status, vault_id=vaultId)}


@router.get("/{candidate_id}")
def api_get(candidate_id: str) -> dict:
    c = get_candidate(candidate_id)
    if not c:
        raise HTTPException(status_code=404, detail="candidate not found")
    return {"candidate": c}


@router.get("/{candidate_id}/preview")
def api_preview(candidate_id: str) -> dict:
    c = get_candidate(candidate_id)
    if not c:
        raise HTTPException(status_code=404, detail="candidate not found")
    return {
        "candidateId": candidate_id,
        "candidateType": c["candidateType"],
        "targetNotePath": c["targetNotePath"],
        "targetHeading": c["targetHeading"],
        "preview": c["markdownPatch"],
    }


@router.post("/{candidate_id}/approve")
def api_approve(candidate_id: str, _req: DecisionRequest | None = None) -> dict:
    c = decide(candidate_id, "APPROVED")
    if c is None:
        raise HTTPException(status_code=409, detail="candidate is not pending or does not exist")
    _publish(T.NOTE_UPDATE_APPROVED, c)
    return {"status": "APPROVED", "candidate": c}


@router.post("/{candidate_id}/reject")
def api_reject(candidate_id: str, _req: DecisionRequest | None = None) -> dict:
    c = decide(candidate_id, "REJECTED")
    if c is None:
        raise HTTPException(status_code=409, detail="candidate is not pending or does not exist")
    _publish(T.NOTE_UPDATE_REJECTED, c)
    return {"status": "REJECTED", "candidate": c}
