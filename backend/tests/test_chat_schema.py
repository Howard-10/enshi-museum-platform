from app.schemas.chat import ChatResponse, Citation


def test_chat_response_supports_internal_evidence_and_notice() -> None:
    response = ChatResponse(
        session_id="session",
        answer="Evidence-first answer",
        intent="knowledge",
        answer_scope="internal_only",
        notice="No external calls were made.",
        citations=[
            Citation(
                id="chunk",
                source_type="internal",
                document_id="document",
                chunk_id="chunk",
                title="Source",
                excerpt="Relevant museum material",
            )
        ],
    )

    assert response.citations[0].source_type == "internal"
    assert response.answer_scope == "internal_only"
    assert response.evidence_status == "insufficient"
