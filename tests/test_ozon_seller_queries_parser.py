from dataclasses import fields
from decimal import Decimal
from pathlib import Path

import pytest

from backend.domain.product_query import (
    PRODUCT_QUERY_PAYLOAD_FIELDS, ParsedSellerQueriesReport, ProductQueryPositionState,
    ProductQuerySnapshot, SellerQueriesConflictingObservationRows,
    SellerQueriesIncompatibleReportSchema, SellerQueriesInvalidGeneratedAt,
    SellerQueriesInvalidProductContext, SellerQueriesInvalidReportPeriod,
    SellerQueriesWrongReportType, product_query_payload_sha256,
)
from backend.ingestion.ozon_seller_queries_xlsx import parse_ozon_seller_queries_xlsx
from tests.xlsx_factory import (
    OZON_SELLER_QUERIES_HEADERS as H, build_ozon_products_workbook,
    build_ozon_query_metrics_workbook, build_ozon_search_visibility_workbook,
    build_ozon_seller_queries_workbook,
)


def _parse(tmp_path: Path, **kwargs):
    path = tmp_path / "seller.xlsx"
    path.write_bytes(build_ozon_seller_queries_workbook(**kwargs))
    return parse_ozon_seller_queries_xlsx(path)


def _row(query="синтетический запрос", **changes):
    row = dict(zip(H[3:], (query, "1 000", "900", "1", "10%", "2%", "20", "5 000 ₽"), strict=True))
    row.update(changes)
    return row


def test_domain_payload_is_decimal_canonical():
    assert tuple(f.name for f in fields(ProductQuerySnapshot))[11:] == PRODUCT_QUERY_PAYLOAD_FIELDS
    values = dict(searched_users=1, seen_users=1, position_state=ProductQueryPositionState.SOURCE_ZERO,
                  average_position=None, search_to_card_conversion_pct=Decimal("2.480"),
                  search_to_order_conversion_pct=Decimal("0"), ordered_units=0,
                  ordered_revenue_rub=Decimal("0"))
    assert product_query_payload_sha256(values) == product_query_payload_sha256(
        {**values, "search_to_card_conversion_pct": Decimal("2.48")})


def test_valid_workbook_returns_contract(tmp_path):
    report = _parse(tmp_path)
    assert isinstance(report, ParsedSellerQueriesReport)
    assert (report.rows_seen, len(report.rows), report.duplicate_input_rows) == (1, 1, 0)


@pytest.mark.parametrize("mutation", [
    {"extra_sheet": True}, {"merged_cells": ("A5:B5",)},
    {"headers": ("wrong", *H[1:])}, {"formula_cells": {"A5": "=1"}},
    {"formula_cells": {"A1": "=1"}}, {"formula_cells": {"A7": "business"}},
    {"formula_cells": {"D8": "business"}},
    {"rows": ({"SKU": "business", **_row()},)},
    {"rows": ({"SKU": " ", **{key: None for key in H[3:]}},)},
])
def test_structural_contract_rejects_mutations(tmp_path, mutation):
    with pytest.raises(SellerQueriesIncompatibleReportSchema):
        _parse(tmp_path, **mutation)


def test_semantic_blank_trailing_row_is_ignored(tmp_path):
    blank = {key: "" if index % 2 else None for index, key in enumerate(H)}
    report = _parse(tmp_path, rows=(_row(), blank))
    assert report.rows_seen == 1


@pytest.mark.parametrize("query", [" ", "\u00a0"])
def test_whitespace_only_query_is_not_structural_blank(tmp_path, query):
    report = _parse(tmp_path, rows=({H[3]: query},))
    assert report.rows_seen == 1 and len(report.row_errors) == 1


@pytest.mark.parametrize("factory", [build_ozon_products_workbook, build_ozon_search_visibility_workbook, build_ozon_query_metrics_workbook])
def test_known_foreign_reports_are_wrong_type(tmp_path, factory):
    path = tmp_path / "foreign.xlsx"; path.write_bytes(factory())
    with pytest.raises(SellerQueriesWrongReportType): parse_ozon_seller_queries_xlsx(path)


@pytest.mark.parametrize("kwargs,error", [
    ({"date": "bad"}, SellerQueriesInvalidGeneratedAt), ({"time": "bad"}, SellerQueriesInvalidGeneratedAt),
    ({"period_start": "bad"}, SellerQueriesInvalidReportPeriod),
    ({"period_start": "18/08/2026", "period_end": "17/08/2026"}, SellerQueriesInvalidReportPeriod),
    *[({"ozon_id": value}, SellerQueriesInvalidProductContext) for value in (None, "", 0, -1, True, False)],
])
def test_metadata_and_product_context(tmp_path, kwargs, error):
    with pytest.raises(error): _parse(tmp_path, **kwargs)


@pytest.mark.parametrize("query,expected", [
    ("  запрос  ", "запрос"), ("\u00a0запрос\u00a0", "запрос"),
    ("Два  Слова", "Два  Слова"), ("Ёж!", "Ёж!"), ("00123", "00123"),
])
def test_query_identity_only_trims_edge_spaces(tmp_path, query, expected):
    assert _parse(tmp_path, rows=(_row(query),)).rows[0].query_text == expected


@pytest.mark.parametrize("changes,expected", [
    ({H[4]: "0", H[5]: "0"}, {"searched_users": 0, "seen_users": 0}),
    ({H[4]: "1", H[5]: "2"}, {"seen_users": 2}),
    ({H[6]: "0"}, {"position_state": ProductQueryPositionState.SOURCE_ZERO, "average_position": None}),
    ({H[6]: "123"}, {"position_state": ProductQueryPositionState.KNOWN, "average_position": 123}),
    ({H[7]: "0%", H[8]: "100%"}, {"search_to_card_conversion_pct": Decimal("0"), "search_to_order_conversion_pct": Decimal("100")}),
    ({H[7]: "12,345%"}, {"search_to_card_conversion_pct": Decimal("12.345")}),
    ({H[9]: "0", H[10]: "0 ₽"}, {"ordered_units": 0, "ordered_revenue_rub": Decimal("0")}),
    ({H[10]: "1 234 567 ₽"}, {"ordered_revenue_rub": Decimal("1234567")}),
])
def test_metric_valid_boundaries(tmp_path, changes, expected):
    values = _parse(tmp_path, rows=(_row(**changes),)).rows[0].snapshot_values
    assert all(values[key] == value for key, value in expected.items())

@pytest.mark.parametrize("source", ["4 869 ₽", "4\u202f869 ₽", "4869 ₽"])
def test_revenue_accepts_only_verified_grouping_forms(tmp_path, source):
    assert _parse(tmp_path, rows=(_row(**{H[10]:source}),)).rows[0].snapshot_values["ordered_revenue_rub"] == Decimal("4869")

@pytest.mark.parametrize("source", ["4\u00a0869 ₽", "4\t869 ₽", "4  869 ₽", "4869,00 ₽"])
def test_revenue_does_not_broaden_whitespace_or_decimal_grammar(tmp_path, source):
    report=_parse(tmp_path, rows=(_row(**{H[10]:source}),))
    assert report.rows == () and report.row_errors[0].code == "INVALID_REVENUE"


@pytest.mark.parametrize("coordinate,value", [
    ("G9", "-1"), ("G9", "1,5"), ("G9", ""), ("H9", "-1%"), ("H9", "101%"),
    ("J9", "-1"), ("J9", "1,5"), ("K9", "-1 ₽"), ("K9", "1,5 ₽"), ("D9", "=1"),
])
def test_bad_metrics_and_data_formula_are_recoverable(tmp_path, coordinate, value):
    report = _parse(tmp_path, formula_cells={coordinate: value})
    assert report.rows == () and report.rows_seen == 1 and len(report.row_errors) == 1


def test_duplicate_conflict_and_counter_invariant(tmp_path):
    valid = _row("one"); duplicate = dict(valid); invalid = _row("bad", **{H[6]: "fraction"})
    report = _parse(tmp_path, rows=(valid, _row("two"), invalid, duplicate))
    assert report.duplicate_input_rows == 1
    assert report.rows_seen == len(report.rows) + len(report.row_errors) + report.duplicate_input_rows
    with pytest.raises(SellerQueriesConflictingObservationRows):
        _parse(tmp_path, rows=(valid, _row("one", **{H[5]: "1"})))


def test_zero_usable_is_parser_result_not_fatal(tmp_path):
    report = _parse(tmp_path, rows=(_row(**{H[6]: "bad"}),))
    assert report.rows == () and report.row_errors
