from openai import OpenAI

from .base import EmbeddingProvider, LLMProvider, LLMResult


class OpenAIEmbeddingProvider(EmbeddingProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str, dimension: int):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        resp = self.client.embeddings.create(
            model=self.model, input=texts, dimensions=self.dimension
        )
        return [d.embedding for d in resp.data]


class OpenAILLMProvider(LLMProvider):
    name = "openai"

    SYSTEM_FALLBACK = "You are a helpful assistant that answers only from the provided notes."

    def __init__(self, api_key: str, model: str):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def generate(self, *, system_prompt: str, question: str, context_blocks: list[dict]) -> LLMResult:
        if context_blocks:
            ctx = "\n\n".join(
                f'[{i}] (노트: {b.get("note_title", "")} / 경로: {b.get("path", "")} / '
                f'섹션: {b.get("heading_path", "")})\n{b.get("content", "")}'
                for i, b in enumerate(context_blocks, start=1)
            )
            user = f"질문: {question}\n\n참고 노트:\n{ctx}"
        else:
            user = f"질문: {question}\n\n참고 노트: (검색 결과 없음)"

        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt or self.SYSTEM_FALLBACK},
                {"role": "user", "content": user},
            ],
        )
        choice = resp.choices[0]
        usage = resp.usage
        return LLMResult(
            text=choice.message.content or "",
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            model=self.model,
        )
