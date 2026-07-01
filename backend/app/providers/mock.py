import hashlib
import math
import re

from .base import EmbeddingProvider, LLMProvider, LLMResult

_WORD = re.compile(r"[0-9A-Za-z가-힣]+")


def _tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower()) or [text.lower().strip() or "empty"]


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic, dependency-free embedding.

    Uses a hashed bag-of-words projection so that texts sharing tokens produce
    similar (higher cosine) vectors, while identical input always yields the
    identical vector (required by US-01-03).
    """

    name = "mock"

    def __init__(self, model: str, dimension: int):
        self.model = model
        self.dimension = dimension

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.dimension
        for tok in _tokens(text):
            h = int(hashlib.sha256(tok.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dimension
            sign = 1.0 if (h >> 8) & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]


class MockLLMProvider(LLMProvider):
    """Deterministic LLM stand-in that answers strictly from context blocks."""

    name = "mock"

    def __init__(self, model: str):
        self.model = model

    def generate(self, *, system_prompt: str, question: str, context_blocks: list[dict]) -> LLMResult:
        text = self._build_answer(question, context_blocks)
        prompt_tokens = (len(system_prompt) + len(question) + sum(len(b.get("content", "")) for b in context_blocks)) // 4
        return LLMResult(
            text=text,
            prompt_tokens=prompt_tokens,
            completion_tokens=max(1, len(text) // 4),
            model=self.model,
        )

    @staticmethod
    def _first_sentences(content: str, limit: int = 2) -> str:
        parts = re.split(r"(?<=[.!?。])\s+|\n+", content.strip())
        parts = [p.strip() for p in parts if p.strip()]
        return " ".join(parts[:limit])

    def _build_answer(self, question: str, context_blocks: list[dict]) -> str:
        if not context_blocks:
            return (
                "제공된 Obsidian 노트에서 질문과 관련된 근거를 찾지 못했습니다. "
                "추측하지 않고 근거 부족으로 답변을 보류합니다."
            )
        lines = [f'질문 "{question}" 에 대해 검색된 노트를 근거로 정리하면 다음과 같습니다.', ""]
        for i, b in enumerate(context_blocks[:3], start=1):
            summary = self._first_sentences(b.get("content", ""))
            lines.append(f'- [{i}] "{b.get("note_title", "")}" ({b.get("heading_path", "")}): {summary}')
        lines.append("")
        lines.append("위 내용은 검색된 노트에 근거하며, 자세한 출처는 citation을 참고하세요.")
        return "\n".join(lines)
