"""Chat API: LangGraph orchestration plus evidence retrieval."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db_session
from app.graphs.chat_graph import MEDIA_WORDS, OUT_OF_SCOPE_REQUEST_WORDS, chat_graph
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.conversation import ConversationHistoryResponse, ConversationMessageRead
from app.services.answer_generation import generate_grounded_answer
from app.services.conversation_memory import ConversationMemoryService
from app.services.evidence_gate import evidence_gate
from app.services.rag_pipeline import RagPipeline
from app.services.web_search import (
    WebSearchDisabledError,
    allowed_domains,
    create_web_search_provider,
    monthly_request_count,
    record_search_audit,
)

router = APIRouter()
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, session: DbSession) -> ChatResponse:
    """Run intent detection, evidence retrieval, and answer composition."""

    wants_media = any(word in request.message for word in MEDIA_WORDS)
    requested_media_type = next(
        (
            media_type
            for keyword, media_type in (
                ("视频", "video"),
                ("音频", "audio"),
                ("语音", "audio"),
                ("图片", "image"),
                ("照片", "image"),
            )
            if keyword in request.message
        ),
        None,
    )
    retrieval = await RagPipeline(session).search(
        request.message,
        include_media=wants_media,
        media_type=requested_media_type,
    )
    gate = evidence_gate(request.message, retrieval)
    if gate.get("citation_scope") == "catalog_only":
        retrieval = {**retrieval, "citations": retrieval.get("catalog_citations", [])}
    elif gate.get("citation_scope") == "catalog_with_background":
        catalog_citations = retrieval.get("catalog_citations", [])
        background_citations = [
            citation
            for citation in retrieval.get("citations", [])
            if citation.get("source_type") == "internal"
        ]
        background_citations = sorted(
            background_citations,
            key=lambda citation: -(
                ("三交" in str(citation.get("title", ""))) * 3
                + ("铜镜" in str(citation.get("excerpt", ""))) * 2
                + ("交流" in str(citation.get("excerpt", "")))
            ),
        )[:4]
        retrieval = {
            **retrieval,
            "citations": [*catalog_citations, *background_citations],
        }
    result = chat_graph.invoke(
        {
            "session_id": request.session_id,
            "user_query": request.message,
            "intent": "",
            "answer": "",
            "citations": retrieval["citations"],
            "media": retrieval["media"],
            "retrieval": retrieval,
            "answer_scope": "insufficient_evidence",
            "notice": None,
            "evidence_status": gate["evidence_status"],
            "reason_codes": gate["reason_codes"],
        }
    )
    generated, generation_reason = (None, None)
    external_search_used = False
    external_search_reason: str | None = None
    relation_question = any(word in request.message for word in ("关系", "三交", "交往", "交流", "交融"))
    artifact_names = [
        str(artifact.get("name"))
        for artifact in retrieval.get("artifacts", [])
        if artifact.get("name")
    ]
    compact_query = "".join(
        character for character in request.message if character.isalnum() or "\u4e00" <= character <= "\u9fff"
    )
    queried_artifact_names = [
        name
        for name in artifact_names
        if "".join(character for character in name if character.isalnum() or "\u4e00" <= character <= "\u9fff")
        in compact_query
    ]
    has_direct_relation_evidence = any(
        citation.get("source_type") == "internal"
        and any(name in f"{citation.get('title', '')}{citation.get('excerpt', '')}" for name in queried_artifact_names)
        and any(word in f"{citation.get('title', '')}{citation.get('excerpt', '')}" for word in ("三交", "交往", "交流", "交融"))
        for citation in retrieval.get("citations", [])
    )
    relation_needs_external = relation_question and not has_direct_relation_evidence

    # The local evidence gate is deliberately conservative. When it cannot
    # support a visitor's question, use the approved public-search fallback
    # once, keep those citations separate from museum records, and never write
    # the results back into the knowledge base.
    can_use_external_search = (
        (gate["evidence_status"] == "insufficient" or relation_needs_external)
        and not wants_media
        and not any(word in request.message for word in OUT_OF_SCOPE_REQUEST_WORDS)
        and settings.web_search_enabled
    )
    if (
        (gate["evidence_status"] == "insufficient" or relation_needs_external)
        and not wants_media
        and not any(word in request.message for word in OUT_OF_SCOPE_REQUEST_WORDS)
        and not settings.web_search_enabled
    ):
        external_search_reason = "external_search_unavailable"
    external_query = request.message if relation_question else f"恩施州博物馆 {request.message}"
    if can_use_external_search:
        try:
            request_count = await monthly_request_count(session)
            if request_count >= settings.web_search_monthly_request_limit:
                external_search_reason = "external_search_budget_exhausted"
            else:
                provider = create_web_search_provider(settings)
                external_response = await provider.search(
                    external_query,
                    allowed_domains=allowed_domains(settings),
                )
                external_citations = [
                    {
                        "source_type": "external",
                        "id": f"SRC_{index:03d}",
                        "title": item.title,
                        "url": item.url,
                        "excerpt": item.excerpt,
                        "document_id": None,
                        "chunk_id": None,
                    }
                    for index, item in enumerate(external_response.results, start=1)
                ]
                await record_search_audit(
                    session,
                    session_id=request.session_id,
                    query=external_query,
                    attempt=request_count + 1,
                    provider=settings.web_search_provider,
                    status="success" if external_citations else "empty",
                    request_id=external_response.request_id,
                    latency_ms=external_response.latency_ms,
                    result_domains=[item.domain for item in external_response.results],
                )
                if external_citations:
                    external_search_used = True
                    external_retrieval = {
                        **retrieval,
                        "citations": [
                            *[citation for citation in retrieval.get("citations", []) if citation.get("source_type") == "internal"],
                            *external_citations,
                        ],
                        "catalog_citations": retrieval.get("catalog_citations", []),
                    }
                    generated, generation_reason = await generate_grounded_answer(
                        request.message,
                        external_retrieval,
                    )
                    if generated is not None:
                        result = {
                            **result,
                            **generated,
                            "answer_scope": "external_search",
                            "evidence_status": "sufficient",
                            "reason_codes": [*gate["reason_codes"], "external_search_used"],
                            "notice": "馆内资料没有明确的直接关联证据，本次补充检索了公开资料；以下内容不等同于馆藏档案。",
                        }
                        gate["evidence_status"] = "sufficient"
                        gate["reason_codes"] = result["reason_codes"]
                    else:
                        result = {
                            **result,
                            "answer": "馆内资料暂未明确回答这个问题。我补充找到了一些公开资料，请查看下方来源。需要注意，公开资料不等同于本馆馆藏档案。",
                            "answer_scope": "external_search",
                            "evidence_status": "sufficient",
                            "reason_codes": [
                                *gate["reason_codes"],
                                "external_search_used",
                                generation_reason or "generation_failed",
                            ],
                            "notice": "馆内资料不足，本次补充检索了公开资料；以下内容不等同于馆藏档案。",
                            "citations": external_citations,
                        }
                        gate["evidence_status"] = "sufficient"
                        gate["reason_codes"] = result["reason_codes"]
                else:
                    external_search_reason = "external_search_empty"
        except WebSearchDisabledError:
            external_search_reason = "external_search_unavailable"
        except Exception as error:  # noqa: BLE001 -- search must degrade safely.
            external_search_reason = f"external_search_error:{type(error).__name__}"
            await record_search_audit(
                session,
                session_id=request.session_id,
                query=external_query,
                attempt=1,
                provider=settings.web_search_provider,
                status="error",
                error_type=type(error).__name__,
            )

    if not external_search_used and external_search_reason:
        result["reason_codes"] = [*gate["reason_codes"], external_search_reason]
        if external_search_reason == "external_search_budget_exhausted":
            result["notice"] = "馆内资料不足，外部搜索额度已用完。"
        elif external_search_reason == "external_search_empty":
            result["notice"] = "馆内资料不足，公开资料也未检索到可核验结果。"
        else:
            result["notice"] = "馆内资料不足，外部搜索暂不可用。"

    if relation_needs_external and not external_search_used:
        result["answer"] = "馆内资料没有记载这件文物与三交的直接关联。公开资料补充暂未找到可核验的直接关系，不能把它说成三交的直接证据。"
        result["answer_scope"] = "insufficient_evidence"
        result["citations"] = retrieval.get("citations", [])
        gate["evidence_status"] = "insufficient"
        gate["reason_codes"] = result["reason_codes"]
        if external_search_reason == "external_search_empty":
            result["notice"] = "馆内资料没有明确的直接关联证据，公开资料也未检索到可核验的直接关系。"

    # Media answers are already deterministic and directly backed by the
    # reviewed media links. Do not let the text model contradict a verified
    # audio/video result by looking only at the document excerpts.
    has_verified_media_result = result["intent"] == "media" and bool(retrieval["media"])
    if (
        gate["evidence_status"] == "sufficient"
        and not has_verified_media_result
        and not relation_needs_external
        and not any(word in request.message for word in OUT_OF_SCOPE_REQUEST_WORDS)
    ):
        generated, generation_reason = await generate_grounded_answer(request.message, retrieval)
    if generated is not None and gate["evidence_status"] == "sufficient" and not external_search_used:
        result = {**result, **generated, "notice": "回答基于本轮馆内资料生成，来源可追溯。"}
    elif generation_reason and gate["evidence_status"] == "sufficient":
        result["notice"] = "当前采用馆内资料直答模式，内容来源可追溯。"
        gate["reason_codes"] = [*gate["reason_codes"], generation_reason]
    response = ChatResponse(
        session_id=result["session_id"],
        answer=result["answer"],
        intent=result["intent"],
        answer_scope=result["answer_scope"],
        notice=result["notice"],
        citations=result["citations"],
        media=result["media"],
        unverified_extension=result.get("unverified_extension"),
        evidence_status=gate["evidence_status"],
        reason_codes=gate["reason_codes"],
    )
    await ConversationMemoryService(session).remember_exchange(
        session_id=request.session_id,
        user_content=request.message,
        assistant_content=response.answer,
        citations=[citation.model_dump() for citation in response.citations],
        media=[media.model_dump() for media in response.media],
    )
    return response


@router.get("/{session_id}/history", response_model=ConversationHistoryResponse)
async def get_history(session_id: str, session: DbSession) -> ConversationHistoryResponse:
    """Return recent messages from Redis when warm, otherwise PostgreSQL."""

    source, messages = await ConversationMemoryService(session).recent_messages(session_id)
    return ConversationHistoryResponse(
        session_id=session_id,
        source=source,
        messages=[ConversationMessageRead(**message) for message in messages],
    )
