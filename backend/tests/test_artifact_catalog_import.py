from app.cli.import_artifact_catalog import parse_catalog_worksheet


def test_parser_preserves_source_annotations_without_creating_an_artifact() -> None:
    records = parse_catalog_worksheet(
        "catalog",
        [
            ("时代", "文物名称", "地点", "材质", "图片"),
            ("明", "凤凰八卦铜镜", "恩施", "-", '=_xlfn.DISPIMG("ID_A",1)'),
            (None, "（上一）", None, None, None),
        ],
    )

    assert len(records) == 2
    assert records[0].artifact_name == "凤凰八卦铜镜"
    assert records[0].era == "明"
    assert records[0].material is None
    assert records[1].record_kind == "annotation"
    assert records[1].artifact_name is None


def test_parser_ignores_blank_rows_and_marks_exact_duplicate_candidates() -> None:
    records = parse_catalog_worksheet(
        "catalog",
        [
            ("时代", "文物名称", "地点", "材质", "图片"),
            ("清", "河图洛书", "鹤峰", "陶", None),
            (None, None, None, None, None),
            ("清", "河图洛书", "鹤峰", "陶", None),
        ],
    )

    assert len(records) == 2
    assert records[0].content_fingerprint == records[1].content_fingerprint
