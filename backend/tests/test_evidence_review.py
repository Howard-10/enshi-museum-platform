from types import SimpleNamespace

from app.services.evidence_review import _exact_artifact_match, normalized_name


def test_exact_document_identity_uses_title_or_filename_stem() -> None:
    artifact = SimpleNamespace(id="a1", name="三峡第一碑")
    document = SimpleNamespace(title="三峡第一碑  ", source_filename="/tmp/other.docx")
    assert _exact_artifact_match(document, [artifact]).id == "a1"

    filename_document = SimpleNamespace(title="背景资料", source_filename="C:\\docs\\三峡第一碑.docx")
    assert _exact_artifact_match(filename_document, [artifact]).id == "a1"


def test_exact_document_identity_rejects_ambiguous_matches() -> None:
    first = SimpleNamespace(id="a1", name="三峡第一碑")
    second = SimpleNamespace(id="a2", name="三峡第一碑")
    document = SimpleNamespace(title="三峡第一碑", source_filename="other.docx")
    assert _exact_artifact_match(document, [first, second]) is None


def test_normalized_name_removes_display_punctuation() -> None:
    assert normalized_name("  土司—铁帽（展签） ") == "土司铁帽展签"
