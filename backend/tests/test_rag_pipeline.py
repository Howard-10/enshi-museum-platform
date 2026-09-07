from app.core.config import Settings
from app.services.model_clients import create_chat_client, create_embedding_client
from app.services.model_readiness import get_model_readiness, require_external_model_calls
from app.services.rag_pipeline import deterministic_rerank, reciprocal_rank_fusion
from app.services.web_search import create_web_search_provider, require_web_search


def test_rrf_rewards_a_document_returned_by_multiple_sources() -> None:
    scores = reciprocal_rank_fusion(
        {
            "keyword": ["a", "b", "c"],
            "vector": ["b", "d", "a"],
        }
    )

    assert scores["b"] > scores["c"]
    assert scores["a"] > scores["d"]


def test_deterministic_reranker_prefers_a_more_specific_excerpt() -> None:
    matches = [
        {"chunk_id": "general", "title": "A", "excerpt": "西瓜碑", "score": 1},
        {"chunk_id": "specific", "title": "B", "excerpt": "西瓜碑的音频讲解资料", "score": 1},
    ]

    ranked = deterministic_rerank("西瓜碑音频", matches, {"general": 0.1, "specific": 0.1})

    assert ranked[0]["chunk_id"] == "specific"


def test_external_model_calls_are_disabled_by_default() -> None:
    config = Settings(
        embedding_api_key="would-be-secret",
        embedding_base_url="https://example.invalid/v1",
        embedding_model="embedding-test",
        embedding_dimensions=1024,
    )

    readiness = get_model_readiness(config)

    assert readiness.external_calls_enabled is False
    assert readiness.vector_search_enabled is False
    try:
        require_external_model_calls(config)
    except RuntimeError as error:
        assert "disabled" in str(error)
    else:
        raise AssertionError("External model calls must remain disabled by default")


def test_langchain_client_factories_do_not_initialize_when_calls_are_disabled() -> None:
    config = Settings(
        llm_api_key="would-be-secret",
        llm_base_url="https://example.invalid/v1",
        chat_model="chat-test",
        embedding_api_key="would-be-secret",
        embedding_base_url="https://example.invalid/v1",
        embedding_model="embedding-test",
        embedding_dimensions=1024,
    )

    for factory in (create_embedding_client, create_chat_client):
        try:
            factory(config)
        except RuntimeError as error:
            assert "disabled" in str(error)
        else:
            raise AssertionError("A client factory bypassed the external-call safety switch")


def test_web_search_client_does_not_initialize_when_disabled() -> None:
    config = Settings(
        web_search_enabled=False,
        tavily_api_key="would-be-secret",
        web_search_monthly_request_limit=100,
    )

    for factory in (require_web_search, create_web_search_provider):
        try:
            factory(config)
        except RuntimeError as error:
            assert "disabled" in str(error)
        else:
            raise AssertionError("A web-search client bypassed the safety switch")


def test_web_search_needs_an_explicit_positive_budget() -> None:
    config = Settings(web_search_enabled=True, tavily_api_key="would-be-secret")

    try:
        require_web_search(config)
    except ValueError as error:
        assert "MONTHLY" in str(error)
    else:
        raise AssertionError("Web search must require an explicit positive monthly budget")
