"""Safe operational state responses without exposing credentials."""

from pydantic import BaseModel


class SystemReadinessResponse(BaseModel):
    retrieval_mode: str
    external_model_calls_enabled: bool
    vector_search_enabled: bool
    chat_generation_enabled: bool
    reranker_enabled: bool
    web_search_enabled: bool
    web_search_provider: str
    web_search_monthly_request_limit: int
    web_search_max_requests_per_answer: int
    web_search_allowed_domains: list[str]
    missing_embedding_fields: list[str]
    missing_chat_fields: list[str]
    missing_reranker_fields: list[str]
    documents: int
    child_chunks: int
    catalog_artifacts: int
    media_assets: int
    approved_document_links: int = 0
