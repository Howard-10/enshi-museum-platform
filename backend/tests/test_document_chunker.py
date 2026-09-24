from zipfile import ZipFile

from app.services.document_chunker import (
    ChunkingConfig,
    ParentChildChunker,
    blocks_to_text,
    normalize_text,
    parse_docx_blocks,
)


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


def test_docx_parser_preserves_heading_hierarchy(tmp_path) -> None:
    ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    document = f'''<w:document xmlns:w="{ns}"><w:body>
      <w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>历史背景</w:t></w:r></w:p>
      <w:p><w:r><w:t>第一段内容。</w:t></w:r></w:p>
      <w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>传入时间</w:t></w:r></w:p>
      <w:p><w:r><w:t>第二段内容。</w:t></w:r></w:p>
      <w:sectPr/></w:body></w:document>'''
    styles = f'''<w:styles xmlns:w="{ns}"><w:style w:styleId="Heading1"><w:name w:val="heading 1"/></w:style><w:style w:styleId="Heading2"><w:name w:val="heading 2"/></w:style></w:styles>'''
    path = tmp_path / "sample.docx"
    with ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document)
        archive.writestr("word/styles.xml", styles)

    blocks = parse_docx_blocks(path)
    assert [(block.content, block.heading_level) for block in blocks] == [
        ("历史背景", 1),
        ("第一段内容。", None),
        ("传入时间", 2),
        ("第二段内容。", None),
    ]
    parents = ParentChildChunker(ChunkingConfig(parent_size=100, child_size=60, child_overlap=10)).split_blocks(blocks)
    assert parents[0].metadata["heading_path"] == ["历史背景"]
    assert parents[1].metadata["heading_path"] == ["历史背景", "传入时间"]
    assert "历史背景" in parents[0].content
    assert blocks_to_text(blocks).startswith("历史背景")
