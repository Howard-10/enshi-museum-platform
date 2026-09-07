from app.services.document_chunker import ChunkingConfig, ParentChildChunker, normalize_text


def test_normalize_text_keeps_paragraphs() -> None:
    assert normalize_text("  第一段\r\n\r\n\r\n第二段  ") == "第一段\n\n第二段"


def test_parent_child_chunking_keeps_children_inside_parent_context() -> None:
    text = "。".join([f"第{i}句介绍恩施文物" for i in range(60)]) + "。"
    chunker = ParentChildChunker(
        ChunkingConfig(parent_size=120, parent_overlap=20, child_size=48, child_overlap=8)
    )

    parents = chunker.split(text)

    assert len(parents) > 1
    assert all(parent.children for parent in parents)
    assert all(len(child.content) <= 48 for parent in parents for child in parent.children)
    assert [child.sequence for parent in parents for child in parent.children] == list(
        range(sum(len(parent.children) for parent in parents))
    )
