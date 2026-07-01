from abc import ABC, abstractmethod
from dataclasses import dataclass


class EmbeddingProvider(ABC):
    name: str = "base"
    model: str = ""
    dimension: int = 0

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


@dataclass
class LLMResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    model: str


class LLMProvider(ABC):
    name: str = "base"
    model: str = ""

    @abstractmethod
    def generate(self, *, system_prompt: str, question: str, context_blocks: list[dict]) -> LLMResult:
        """Generate an answer grounded in the given context blocks.

        Each context block is a dict with keys: chunk_id, note_title, path,
        heading_path, content.
        """
