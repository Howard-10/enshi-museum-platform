"""Model configuration checks that never invoke an external provider."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings, settings


@dataclass(frozen=True)
class ModelReadiness:
    external_calls_enabled: bool
    vector_search_enabled: bool
    chat_generation_enabled: bool
    reranker_enabled: bool
    missing_embedding_fields: tuple[str, ...]
    missing_chat_fields: tuple[str, ...]
    missing_reranker_fields: tuple[str, ...]

    @property
    def embedding_indexing_ready(self) -> bool:
        return self.external_calls_enabled and not self.missing_embedding_fields

    @property
    def retrieval_mode(self) -> str:
        return "hybrid" if self.vector_search_enabled else "keyword"


def missing_fields(**values: str | int | None) -> tuple[str, ...]:
    return tuple(name for name, value in values.items() if value in (None, ""))


def get_model_readiness(config: Settings = settings) -> ModelReadiness:
    """Return a safe configuration report without constructing API clients."""

    embedding_missing = missing_fields(
        EMBEDDING_API_KEY=config.embedding_api_key,
        EMBEDDING_BASE_URL=config.embedding_base_url,
        EMBEDDING_MODEL=config.embedding_model,
        EMBEDDING_DIMENSIONS=config.embedding_dimensions,
    )
    chat_missing = missing_fields(
        LLM_API_KEY=config.llm_api_key,
        LLM_BASE_URL=config.llm_base_url,
        CHAT_MODEL=config.chat_model,
    )
    reranker_missing = missing_fields(
        RERANKER_API_KEY=config.reranker_api_key,
        RERANKER_BASE_URL=config.reranker_base_url,
        RERANKER_MODEL=config.reranker_model,
    )
    external_calls_enabled = config.external_model_calls_enabled
    return ModelReadiness(
        external_calls_enabled=external_calls_enabled,
        vector_search_enabled=(
            external_calls_enabled and config.hybrid_retrieval_enabled and not embedding_missing
        ),
        chat_generation_enabled=(
            external_calls_enabled and config.chat_generation_enabled and not chat_missing
        ),
        reranker_enabled=external_calls_enabled and not reranker_missing,
        missing_embedding_fields=embedding_missing,
        missing_chat_fields=chat_missing,
        missing_reranker_fields=reranker_missing,
    )


class ExternalModelCallsDisabledError(RuntimeError):
    """Raised by future model workers unless the user explicitly enables them."""


def require_external_model_calls(config: Settings = settings) -> None:
    if not config.external_model_calls_enabled:
        raise ExternalModelCallsDisabledError(
            "External model calls are disabled. Set EXTERNAL_MODEL_CALLS_ENABLED=true only after approval."
        )
