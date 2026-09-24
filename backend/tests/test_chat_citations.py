from app.api.v1.routes.chat import _deduplicate_citations


def test_deduplicate_citations_removes_identical_visible_evidence() -> None:
    citations = [
        {
            "source_type": "internal",
            "title": "西瓜碑",
            "excerpt": "同一段证据",
            "url": None,
            "id": "chunk-1",
        },
        {
            "source_type": "internal",
            "title": "西瓜碑",
            "excerpt": "同一段证据",
            "url": None,
            "id": "chunk-2",
        },
        {
            "source_type": "internal",
            "title": "西瓜碑",
            "excerpt": "另一段证据",
            "url": None,
            "id": "chunk-3",
        },
    ]

    unique = _deduplicate_citations(citations)

    assert [item["id"] for item in unique] == ["chunk-1", "chunk-3"]
