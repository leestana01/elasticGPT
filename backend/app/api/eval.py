from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import settings
from ..eval.evaluator import compare_latest, get_run, list_runs, run_evaluation
from ..eval.golden import list_items, register_item

router = APIRouter(prefix="/api/eval", tags=["evaluation"])


class GoldenItemRequest(BaseModel):
    vaultId: str | None = None
    question: str
    expectedNotePaths: list[str] = []
    expectedChunkIds: list[str] = []
    expectedAnswer: str | None = None
    mustCite: list[str] = []
    shouldAbstain: bool = False


class RunRequest(BaseModel):
    vaultId: str | None = None
    topK: int | None = None
    includeAnswer: bool = True


@router.get("/golden")
def api_golden_list(vaultId: str | None = None) -> dict:
    return {"items": list_items(vaultId or settings.default_vault_id)}


@router.post("/golden")
def api_golden_register(req: GoldenItemRequest) -> dict:
    item = register_item(
        req.vaultId or settings.default_vault_id,
        {
            "question": req.question,
            "expected_note_paths": req.expectedNotePaths,
            "expected_chunk_ids": req.expectedChunkIds,
            "expected_answer": req.expectedAnswer,
            "must_cite": req.mustCite,
            "should_abstain": req.shouldAbstain,
        },
    )
    return {"item": item}


@router.post("/run")
def api_run(req: RunRequest) -> dict:
    return run_evaluation(req.vaultId, req.topK, req.includeAnswer)


@router.get("/runs")
def api_runs(vaultId: str | None = None) -> dict:
    return {"runs": list_runs(vaultId)}


@router.get("/runs/{run_id}")
def api_run_get(run_id: str) -> dict:
    r = get_run(run_id)
    if not r:
        raise HTTPException(status_code=404, detail="eval run not found")
    return {"run": r}


@router.get("/compare")
def api_compare(vaultId: str | None = None) -> dict:
    return compare_latest(vaultId)
