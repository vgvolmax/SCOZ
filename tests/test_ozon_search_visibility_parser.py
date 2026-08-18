from dataclasses import FrozenInstanceError, fields, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO

import pytest
from openpyxl import load_workbook

from backend.domain.lineage import ImportStatus, SourceArtifact, normalized_payload_sha256
from backend.domain.product_snapshot import SnapshotWriteKind
from backend.domain.search_visibility import (
    SEARCH_VISIBILITY_PAYLOAD_FIELDS,
    Cluster,
    CpoState,
    OzonSearchVisibilityError,
    OzonSearchVisibilityImportFailure,
    OzonSearchVisibilityImportResult,
    OzonSearchVisibilityImportSummary,
    ParsedSearchVisibilityReport,
    ParsedSearchVisibilityRow,
    SearchQuery,
    SearchVisibilityConcurrentImportConflict,
    SearchVisibilityConflictingObservationRows,
    SearchVisibilityImportPersistenceError,
    SearchVisibilityIncompatibleReportSchema,
    SearchVisibilityInvalidMetricValue,
    SearchVisibilityInvalidObservedAt,
    SearchVisibilityInvalidProductIdentity,
    SearchVisibilityInvalidSearchContext,
    SearchVisibilityNoUsableRows,
    SearchVisibilityRowError,
    SearchVisibilitySnapshot,
    SearchVisibilityUnsupportedUploadMediaType,
    SearchVisibilityUnsupportedWorkbook,
    SearchVisibilityUploadTooLarge,
    SearchVisibilityWriteResult,
    SearchVisibilityWrongReportType,
    search_visibility_payload_sha256,
    search_visibility_snapshot_payload,
)
from backend.ingestion.ozon_search_visibility_xlsx import parse_ozon_search_visibility_xlsx
from tests.xlsx_factory import (
    OZON_SEARCH_VISIBILITY_HEADERS,
    build_ozon_search_visibility_workbook,
)


FIELD_SEQUENCES = {
    SearchQuery: ("id", "query_text", "created_at"),
    Cluster: ("id", "name", "created_at"),
    SearchVisibilitySnapshot: (
        "id", "product_id", "search_query_id", "cluster_id", "observed_at",
        "revision", "supersedes_snapshot_id", "payload_sha256",
        "import_batch_id", "source_artifact_id", "imported_at", "source_title",
        "seller_name", "position", "overall_score", "promotion_status", "cpc_rub",
        "promotion_strategy", "cpo_state", "cpo_pct", "relevance_score", "rating",
        "reviews_count", "buyer_price_rub", "popularity_score", "ozon_promotion",
        "delivery_label", "delivery_min_days", "delivery_max_days", "price_index_pct",
    ),
    SearchVisibilityWriteResult: ("kind", "snapshot"),
    SearchVisibilityRowError: ("row", "code", "message"),
    ParsedSearchVisibilityRow: ("source_row", "ozon_product_id", "snapshot_values", "payload_sha256"),
    ParsedSearchVisibilityReport: (
        "observed_at", "query_text", "cluster_name", "declared_rows", "rows_seen",
        "rows", "row_errors", "duplicate_input_rows", "warnings_count",
    ),
    OzonSearchVisibilityImportResult: (
        "import_batch_id", "report_type", "status", "observed_at", "query_text",
        "cluster_name", "declared_rows", "rows_seen", "rows_accepted", "rows_skipped",
        "duplicate_observations", "new_observations", "corrected_revisions",
        "warnings_count", "row_errors_total", "row_errors", "row_errors_truncated",
        "source_artifact", "imported_at",
    ),
    OzonSearchVisibilityImportSummary: (
        "import_batch_id", "source", "import_kind", "status", "observed_at", "query_text",
        "cluster_name", "declared_rows", "rows_seen", "rows_accepted", "rows_skipped",
        "duplicate_observations", "new_observations", "corrected_revisions",
        "warnings_count", "row_errors_total", "started_at", "finished_at", "source_artifact",
    ),
}


@pytest.mark.parametrize(("domain_type", "expected"), FIELD_SEQUENCES.items())
def test_domain_dataclasses_are_frozen_with_exact_field_order(domain_type, expected):
    assert is_dataclass(domain_type)
    assert tuple(field.name for field in fields(domain_type)) == expected
    values = {field.name: None for field in fields(domain_type)}
    instance = domain_type(**values)
    with pytest.raises(FrozenInstanceError):
        setattr(instance, fields(domain_type)[0].name, 1)


def test_error_hierarchy_and_failure_contract():
    error_types = (
        SearchVisibilityUnsupportedWorkbook, SearchVisibilityWrongReportType,
        SearchVisibilityIncompatibleReportSchema, SearchVisibilityInvalidObservedAt,
        SearchVisibilityInvalidSearchContext, SearchVisibilityInvalidProductIdentity,
        SearchVisibilityInvalidMetricValue, SearchVisibilityConflictingObservationRows,
        SearchVisibilityNoUsableRows, SearchVisibilityConcurrentImportConflict,
        SearchVisibilityUploadTooLarge, SearchVisibilityUnsupportedUploadMediaType,
        SearchVisibilityImportPersistenceError,
    )
    assert all(issubclass(error_type, OzonSearchVisibilityError) for error_type in error_types)
    error = SearchVisibilityInvalidMetricValue("bad")
    failure = OzonSearchVisibilityImportFailure(error=error, result=None)
    assert failure.error is error
    assert failure.result is None
    assert str(failure) == "bad"


def test_cpo_and_write_kind_contracts():
    assert tuple(state.value for state in CpoState) == ("ACTIVE", "DISABLED", "UNAVAILABLE")
    assert fields(SearchVisibilityWriteResult)[0].type is SnapshotWriteKind


def _payload() -> dict[str, object]:
    return {
        "source_title": "Синтетический товар", "seller_name": "Синтетический продавец",
        "position": 1, "overall_score": Decimal("52.600"), "promotion_status": "Продвигается",
        "cpc_rub": Decimal("22.30"), "promotion_strategy": "Автостратегия",
        "cpo_state": CpoState.ACTIVE, "cpo_pct": Decimal("10.0"),
        "relevance_score": Decimal("84.10"), "rating": None, "reviews_count": None,
        "buyer_price_rub": Decimal("2947"), "popularity_score": Decimal("2.60"),
        "ozon_promotion": True, "delivery_label": "1-2 дня", "delivery_min_days": 1,
        "delivery_max_days": 2, "price_index_pct": Decimal("5.0"),
    }


def test_payload_contract_canonicalizes_without_changing_json_types():
    assert SEARCH_VISIBILITY_PAYLOAD_FIELDS == (
        "source_title", "seller_name", "position", "overall_score", "promotion_status",
        "cpc_rub", "promotion_strategy", "cpo_state", "cpo_pct", "relevance_score",
        "rating", "reviews_count", "buyer_price_rub", "popularity_score", "ozon_promotion",
        "delivery_label", "delivery_min_days", "delivery_max_days", "price_index_pct",
    )
    canonical = search_visibility_snapshot_payload(_payload())
    assert canonical["overall_score"] == "52.6"
    assert canonical["cpo_state"] == "ACTIVE"
    assert canonical["ozon_promotion"] is True
    assert canonical["rating"] is None
    assert search_visibility_payload_sha256(_payload()) == normalized_payload_sha256(canonical)
    equivalent = _payload() | {"overall_score": Decimal("52.6")}
    assert search_visibility_payload_sha256(_payload()) == search_visibility_payload_sha256(equivalent)
    with pytest.raises(ValueError):
        search_visibility_snapshot_payload({key: value for key, value in _payload().items() if key != "position"})
    with pytest.raises(ValueError):
        search_visibility_snapshot_payload(_payload() | {"extra": 1})


def test_synthetic_workbook_default_structure_and_mutations():
    workbook = load_workbook(BytesIO(build_ozon_search_visibility_workbook()))
    assert workbook.sheetnames == ["Поисковая видимость"]
    sheet = workbook.active
    assert tuple(sheet.cell(row=row, column=1).value for row in range(1, 6)) == (
        "Дата: 17/08/2026", "Запрос: тестовый запрос", "Время: 03:55 +00",
        "Регион: г. Тестоград, Россия", "Сколько позиций в выдаче: 1",
    )
    assert all(sheet.cell(6, column).value is None for column in range(1, 17))
    assert tuple(sheet.cell(7, column).value for column in range(1, 17)) == OZON_SEARCH_VISIBILITY_HEADERS
    assert OZON_SEARCH_VISIBILITY_HEADERS[6] == "Ставка\nОплата за клик"
    assert OZON_SEARCH_VISIBILITY_HEADERS[8] == "Ставка\nОплата за заказ"
    assert all(sheet.cell(8, column).value is None for column in range(1, 17))
    assert sheet["A9"].value == "Справочная строка"
    assert sheet["A10"].value == "1" and sheet["B10"].value == 100000001
    workbook.close()

    mutated = load_workbook(BytesIO(build_ozon_search_visibility_workbook(
        query="другой запрос", cluster="г. Иной, Россия", date="18/08/2026",
        time="04:01 +00", declared_rows=7, headers=("X",) * 16,
        rows=({"X": "last"},), extra_sheet=True, row_6_values={"A": "six"},
        row_8_values={"B": ""}, row_9_values={"C": "help"},
        merged_ranges=("A11:B11",), formula_cells={"D9": "=1+1"},
        q_to_z_values={"Q10": "outside"},
    )))
    sheet = mutated.worksheets[0]
    assert sheet["A1"].value == "Дата: 18/08/2026"
    assert sheet["A2"].value == "Запрос: другой запрос"
    assert sheet["A3"].value == "Время: 04:01 +00"
    assert sheet["A4"].value == "Регион: г. Иной, Россия"
    assert sheet["A5"].value == "Сколько позиций в выдаче: 7"
    assert sheet["A6"].value == "six"
    assert sheet["B8"].value is None and sheet["B8"].data_type == "inlineStr"
    assert sheet["C9"].value == "help" and sheet["D9"].data_type == "f"
    assert sheet["Q10"].value == "outside" and len(mutated.worksheets) == 2
    assert "A11:B11" in sheet.merged_cells
    mutated.close()


def _parse(tmp_path, **kwargs):
    path = tmp_path / "upload.part"
    path.write_bytes(build_ozon_search_visibility_workbook(**kwargs))
    return parse_ozon_search_visibility_xlsx(path)


def _row(**changes):
    values = (
        "1", 100000001, "Synthetic product", "Synthetic seller", "0,685",
        "Продвигается", "22,32 ₽", "Автостратегия", "10%", "84,10",
        "4,8 (180 шт.)", "2 947 ₽", "2,60", "Да", "1-2 дня", "5,0%",
    )
    result = dict(zip(OZON_SEARCH_VISIBILITY_HEADERS, values, strict=True))
    result.update(changes)
    return result


def test_parser_valid_context_payload_and_edge_only_identity_cleanup(tmp_path):
    report = _parse(tmp_path, query=" \u00a0Точный  запрос\u00a0 ", cluster=" г. Москва, Россия\u00a0")
    assert report.observed_at == datetime(2026, 8, 17, 3, 55, tzinfo=timezone.utc)
    assert report.query_text == "Точный  запрос"
    assert report.cluster_name == "г. Москва, Россия"
    assert report.rows_seen == report.declared_rows == 1
    assert report.rows[0].snapshot_values["position"] == 1
    assert report.rows[0].snapshot_values["overall_score"] == Decimal("0.685")
    assert report.rows[0].snapshot_values["reviews_count"] == 180


def test_parser_accepts_style_only_qz_blank_rows_and_row9_text(tmp_path):
    report = _parse(tmp_path, row_8_values={"B": ""}, row_9_values={"P": "arbitrary help"})
    assert len(report.rows) == 1


@pytest.mark.parametrize("kwargs", [
    {"q_to_z_values": {"Q10": "business"}}, {"row_6_values": {"A": " "}},
    {"row_8_values": {"A": " "}}, {"formula_cells": {"D9": "=1+1"}},
    {"extra_sheet": True}, {"merged_ranges": ("A10:B10",)},
    {"headers": OZON_SEARCH_VISIBILITY_HEADERS[:-1] + ("wrong",)},
])
def test_parser_rejects_incompatible_structure(tmp_path, kwargs):
    with pytest.raises(SearchVisibilityIncompatibleReportSchema):
        _parse(tmp_path, **kwargs)


def test_parser_classifies_unreadable_and_foreign_workbooks(tmp_path):
    path = tmp_path / "upload.part"
    path.write_bytes(b"not xlsx")
    with pytest.raises(SearchVisibilityUnsupportedWorkbook):
        parse_ozon_search_visibility_xlsx(path)
    workbook = load_workbook(BytesIO(build_ozon_search_visibility_workbook()))
    workbook.active["A1"] = "Foreign report"
    output = BytesIO(); workbook.save(output); workbook.close(); path.write_bytes(output.getvalue())
    with pytest.raises(SearchVisibilityWrongReportType):
        parse_ozon_search_visibility_xlsx(path)


@pytest.mark.parametrize("kwargs,error", [
    ({"date": "31/02/2026"}, SearchVisibilityInvalidObservedAt),
    ({"date": "2026-08-17"}, SearchVisibilityInvalidObservedAt),
    ({"time": "03:55 +03"}, SearchVisibilityInvalidObservedAt),
    ({"query": " \u00a0 "}, SearchVisibilityInvalidSearchContext),
    ({"cluster": "\u00a0"}, SearchVisibilityInvalidSearchContext),
    ({"declared_rows": 2}, SearchVisibilityIncompatibleReportSchema),
    ({"declared_rows": 0}, SearchVisibilityIncompatibleReportSchema),
])
def test_parser_rejects_invalid_context_and_coverage(tmp_path, kwargs, error):
    with pytest.raises(error):
        _parse(tmp_path, **kwargs)


def test_parser_cpo_reviews_grouping_boolean_delivery_and_high_position(tmp_path):
    rows = (
        _row(**{"ID товара": 1, "Позиция": "1147", "Ставка\nОплата за заказ": "Выключено", "Отзывы": "— ", "Акции от Ozon": "Нет", "Срок доставки": "15-36 дней"}),
        _row(**{"ID товара": 2, "Ставка\nОплата за заказ": "—", "Отзывы": "4,8 (33 026 шт.)", "Цена для покупателя": "17 338 ₽"}),
    )
    report = _parse(tmp_path, rows=rows)
    first, second = (row.snapshot_values for row in report.rows)
    assert (first["position"], first["cpo_state"], first["rating"], first["ozon_promotion"]) == (1147, CpoState.DISABLED, None, False)
    assert second["cpo_state"] is CpoState.UNAVAILABLE and second["reviews_count"] == 33026


@pytest.mark.parametrize("column,value,code", [
    ("ID товара", True, "INVALID_PRODUCT_IDENTITY"),
    ("ID товара", "1", "INVALID_PRODUCT_IDENTITY"),
    ("ID товара", 1.5, "INVALID_PRODUCT_IDENTITY"),
    ("Позиция", "0", "INVALID_POSITION"),
    ("Название товара", None, "INVALID_METRIC_VALUE"),
    ("Ставка\nОплата за клик", "22,3 ₽", "INVALID_METRIC_VALUE"),
    ("Ставка\nОплата за заказ", "-", "INVALID_CPO_STATE"),
    ("Отзывы", "—", "INVALID_REVIEWS"),
    ("Отзывы", " — ", "INVALID_REVIEWS"),
    ("Отзывы", "", "INVALID_REVIEWS"),
    ("Отзывы", "-", "INVALID_REVIEWS"),
    ("Отзывы", "Нет данных", "INVALID_REVIEWS"),
    ("Акции от Ozon", "да", "INVALID_METRIC_VALUE"),
    ("Срок доставки", "2-1 дня", "INVALID_DELIVERY"),
    ("Индекс цен", "5%", "INVALID_METRIC_VALUE"),
])
def test_parser_returns_exact_recoverable_row_errors(tmp_path, column, value, code):
    report = _parse(tmp_path, rows=(_row(**{column: value}),))
    assert report.rows == ()
    assert report.row_errors[0].row == 10
    assert report.row_errors[0].code == code


def test_parser_deduplicates_identical_and_rejects_conflicting_product_rows(tmp_path):
    same = _row()
    report = _parse(tmp_path, rows=(same, same))
    assert len(report.rows) == 1 and report.duplicate_input_rows == report.warnings_count == 1
    with pytest.raises(SearchVisibilityConflictingObservationRows):
        _parse(tmp_path, rows=(same, _row(**{"Позиция": "2"})))


def test_parser_product_formula_is_recoverable(tmp_path):
    report = _parse(tmp_path, formula_cells={"E10": "=1+1"})
    assert report.rows == ()
    assert report.row_errors == (SearchVisibilityRowError(10, "INVALID_METRIC_VALUE", "Некорректное значение показателя."),)
