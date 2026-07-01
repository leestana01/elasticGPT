import logging

from ..config import settings
from ..db.database import session_scope
from ..db.models import EvalRun
from ..events.ids import new_id
from ..rag.context import build_context
from ..rag.generation import generate_answer
from ..rag.retrieval import hybrid_retrieve
from .golden import list_items

log = logging.getLogger("eval.evaluator")

_ABSTAIN_MARKERS = ("모른", "찾지 못", "관련된 정보가 없", "보류", "확인할 수 없", "정보가 부족")


def _avg(xs: list[float]):
    return round(sum(xs) / len(xs), 3) if xs else None


def run_evaluation(vault_id: str | None = None, top_k: int | None = None, include_answer: bool = True) -> dict:
    """Evaluate retrieval (Recall@K, MRR, Hit Rate) and, optionally, answer +
    citation quality against the Golden Set (US-10-03 / US-10-04)."""
    vault_id = vault_id or settings.default_vault_id
    top_k = top_k or settings.default_top_k
    items = list_items(vault_id)

    per_query = []
    recalls, rrs, hits = [], [], 0
    cite_ok = cite_total = 0
    ground_ok = ground_total = 0
    abstain_ok = abstain_total = 0

    for it in items:
        retr = hybrid_retrieve(vault_id, it["question"], top_k=top_k)
        ordered_paths: list[str] = []
        for r in retr["results"]:
            if r["path"] not in ordered_paths:
                ordered_paths.append(r["path"])
        top = ordered_paths[:top_k]
        expected = it["expected_note_paths"]
        result = {"question": it["question"], "expected": expected, "retrievedTop": top[:5]}

        if expected:
            found = [e for e in expected if e in top]
            recall = len(found) / len(expected)
            recalls.append(recall)
            rank = next((i + 1 for i, p in enumerate(top) if p in expected), 0)
            rr = 1.0 / rank if rank else 0.0
            rrs.append(rr)
            if rank:
                hits += 1
            result.update({"recall": round(recall, 3), "rank": rank, "reciprocalRank": round(rr, 3)})

        if include_answer:
            ctx = build_context(retr["results"])
            gen = generate_answer(it["question"], ctx)
            cited_paths = [c.get("path") for c in gen["citations"]]
            result["hasCitations"] = len(gen["citations"]) > 0

            if it["must_cite"]:
                cite_total += 1
                ok = any(m in cited_paths for m in it["must_cite"])
                cite_ok += 1 if ok else 0
                result["citationCorrect"] = ok

            if expected:
                ground_total += 1
                grounded = any(e in cited_paths for e in expected)
                ground_ok += 1 if grounded else 0
                result["grounded"] = grounded

            if it["should_abstain"]:
                abstain_total += 1
                answer = gen["answer"]
                abstained = gen["insufficientContext"] or any(m in answer for m in _ABSTAIN_MARKERS)
                abstain_ok += 1 if abstained else 0
                result["abstainedCorrectly"] = abstained

        per_query.append(result)

    metrics = {
        "topK": top_k,
        "itemCount": len(items),
        "recallAtK": _avg(recalls),
        "mrr": _avg(rrs),
        "hitRate": round(hits / len(recalls), 3) if recalls else None,
        "citationAccuracy": round(cite_ok / cite_total, 3) if cite_total else None,
        "groundednessRate": round(ground_ok / ground_total, 3) if ground_total else None,
        "abstainAccuracy": round(abstain_ok / abstain_total, 3) if abstain_total else None,
    }

    run_id = new_id("eval")
    with session_scope() as session:
        session.add(EvalRun(run_id=run_id, vault_id=vault_id, top_k=top_k, metrics=metrics, results=per_query))
    log.info("eval run %s: %s", run_id, metrics)
    return {"runId": run_id, "metrics": metrics, "results": per_query}


def _run_dict(r: EvalRun) -> dict:
    return {
        "runId": r.run_id,
        "vaultId": r.vault_id,
        "topK": r.top_k,
        "metrics": r.metrics or {},
        "results": r.results or [],
        "createdAt": r.created_at.isoformat() if r.created_at else None,
    }


def list_runs(vault_id: str | None = None, limit: int = 20) -> list[dict]:
    with session_scope() as session:
        q = session.query(EvalRun)
        if vault_id:
            q = q.filter(EvalRun.vault_id == vault_id)
        return [_run_dict(r) for r in q.order_by(EvalRun.created_at.desc()).limit(limit).all()]


def get_run(run_id: str) -> dict | None:
    with session_scope() as session:
        r = session.get(EvalRun, run_id)
        return _run_dict(r) if r else None


def compare_latest(vault_id: str | None = None) -> dict:
    """Compare the two most recent runs so a config change can be judged."""
    vault_id = vault_id or settings.default_vault_id
    runs = list_runs(vault_id, limit=2)
    if len(runs) < 2:
        return {"current": runs[0] if runs else None, "previous": None, "deltas": {}}
    current, previous = runs[0]["metrics"], runs[1]["metrics"]
    deltas = {}
    for k, v in current.items():
        pv = previous.get(k)
        if isinstance(v, (int, float)) and isinstance(pv, (int, float)):
            deltas[k] = round(v - pv, 3)
    return {"current": runs[0], "previous": runs[1], "deltas": deltas}
