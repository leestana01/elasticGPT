from ..config import settings
from .base import EmbeddingProvider, LLMProvider
from .mock import MockEmbeddingProvider, MockLLMProvider


def use_openai() -> bool:
    """OpenAI is used only when explicitly selected AND a key is present.

    Otherwise we fall back to the deterministic mock provider (US-01-03).
    """
    return settings.ai_provider.lower() == "openai" and bool(settings.openai_api_key.strip())


def active_provider_name() -> str:
    return "openai" if use_openai() else "mock"


def get_embedding_provider() -> EmbeddingProvider:
    if use_openai():
        from .openai_provider import OpenAIEmbeddingProvider

        return OpenAIEmbeddingProvider(
            settings.openai_api_key, settings.embedding_model, settings.embedding_dim
        )
    return MockEmbeddingProvider(f"mock-{settings.embedding_model}", settings.embedding_dim)


def get_llm_provider() -> LLMProvider:
    if use_openai():
        from .openai_provider import OpenAILLMProvider

        return OpenAILLMProvider(settings.openai_api_key, settings.chat_model)
    return MockLLMProvider(f"mock-{settings.chat_model}")
