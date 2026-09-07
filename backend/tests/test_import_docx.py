from pathlib import Path

from app.cli.import_docx import infer_artifact_name


def test_infer_artifact_name_from_standard_source_package(tmp_path: Path) -> None:
    root = tmp_path / "文物语料与语音"
    path = root / "史前至隋" / "三峡第一碑" / "三峡第一碑 文字" / "三峡第一碑1.docx"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"placeholder")

    assert infer_artifact_name(path, root) == "三峡第一碑"


def test_infer_artifact_name_leaves_other_layouts_unassigned(tmp_path: Path) -> None:
    root = tmp_path / "raw"
    path = root / "seed-v1" / "唐宋文物" / "西瓜碑.docx"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"placeholder")

    assert infer_artifact_name(path, root) is None


def test_infer_artifact_name_accepts_a_relative_path(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "文物语料与语音"
    path = root / "唐宋" / "西瓜碑" / "西瓜碑文字" / "西瓜碑1.docx"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"placeholder")
    monkeypatch.chdir(tmp_path)

    assert infer_artifact_name(path.relative_to(tmp_path), root.relative_to(tmp_path)) == "西瓜碑"
