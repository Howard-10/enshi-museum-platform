from app.services.xlsx_embedded_images import row_artifact_name


def test_row_artifact_name_ignores_dispimg_formula_and_serial_number() -> None:
    assert row_artifact_name([1, "长江峡江号子", '=_xlfn.DISPIMG("id",1)']) == "长江峡江号子"


def test_row_artifact_name_returns_none_without_readable_label() -> None:
    assert row_artifact_name([1, None, '=_xlfn.DISPIMG("id",1)']) is None
