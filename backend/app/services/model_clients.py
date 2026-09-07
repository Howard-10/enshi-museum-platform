"""LangChain 1.x model client factories guarded by explicit configuration."""

from __future__ import annotations

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.core.config import Settings, settings
from app.services.model_readiness import (
    get_model_readiness,
    require_external_model_calls,
)


def create_embedding_client(config: Settings = settings) -> OpenAIEmbeddings:
    """Create an OpenAI-compatible embedding client only after explicit approval.

    Constructing this client does not run a request. Actual embedding happens in
    the future indexing worker, which is also guarded by the same setting.
    """

    require_external_model_calls(config)
    readiness = get_model_readiness(config)
    if readiness.missing_embedding_fields:
        raise ValueError(
            f"Embedding configuration is incomplete: {', '.join(readiness.missing_embedding_fields)}"
        )
    return OpenAIEmbeddings(
        model=config.embedding_model,
        dimensions=config.embedding_dimensions,
        api_key=config.embedding_api_key,
        base_url=config.embedding_base_url,
        # Qwen's OpenAI-compatible endpoint accepts an array of text strings.
        # Do not let LangChain replace those strings with token-id arrays first.
        check_embedding_ctx_length=False,
        max_retries=2,
    )


async def embed_retrieval_query(query: str, config: Settings = settings) -> list[float]:
    """Embed a visitor query with provider-specific retrieval parameters.

    Qwen indexes knowledge-base passages as ``document`` by default. Its
    retrieval API recommends a directional ``query`` embedding for short user
    questions, while other OpenAI-compatible providers keep the generic path.
    """

    client = create_embedding_client(config)
    if (config.embedding_model or "").startswith("qwen"):
        response = await client.async_client.create(
            input=[query],
            model=config.embedding_model,
            dimensions=config.embedding_dimensions,
            extra_body={"parameters": {"text_type": "query"}},
        )
        if not response.data:
            raise RuntimeError("Embedding provider returned no query vector")
        return list(response.data[0].embedding)
    return await client.aembed_query(query)


def create_chat_client(config: Settings = settings) -> ChatOpenAI:
    """Create an OpenAI-compatible LangChain chat client only after approval."""

    require_external_model_calls(config)
    readiness = get_model_readiness(config)
    if not readiness.chat_generation_enabled:
        raise ValueError(
            f"Chat configuration is incomplete: {', '.join(readiness.missing_chat_fields)}"
        )
    return ChatOpenAI(
        model=config.chat_model,
        api_key=config.llm_api_key,
        base_url=config.llm_base_url,
        temperature=0,
        max_retries=2,
    )
