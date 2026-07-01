import time

from ..providers.base import LLMResult
from ..providers.factory import get_llm_provider
from .prompts import INSUFFICIENT_ANSWER, SYSTEM_PROMPT


def _citation(b: dict) -> dict:
    return {
        "noteTitle": b.get("note_title"),
        "path": b.get("path"),
        "headingPath": b.get("heading_path"),
        "chunkId": b.get("chunk_id"),
        "sourceType": b.get("source_type"),
        "score": b.get("score"),
    }


def generate_answer(question: str, context: dict) -> dict:
    provider = get_llm_provider()
    blocks = context.get("blocks", [])
    start = time.time()

    if context.get("insufficient") or not blocks:
        result = LLMResult(text=INSUFFICIENT_ANSWER, prompt_tokens=0, completion_tokens=0, model=provider.model)
    else:
        result = provider.generate(system_prompt=SYSTEM_PROMPT, question=question, context_blocks=blocks)

    latency_ms = int((time.time() - start) * 1000)
    return {
        "answer": result.text,
        "citations": [_citation(b) for b in blocks],
        "usage": {
            "promptTokens": result.prompt_tokens,
            "completionTokens": result.completion_tokens,
            "model": result.model,
        },
        "latencyMs": latency_ms,
        "insufficientContext": context.get("insufficient", False),
    }
