from dataclasses import fields
from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile
from openpyxl import load_workbook
import pytest
from backend.domain.query_metric import *
from tests.xlsx_factory import build_ozon_query_metrics_workbook, OZON_QUERY_METRICS_HEADERS

def test_contract_and_payload():
    assert tuple(f.name for f in fields(QueryMetricSnapshot))[10:] == QUERY_METRIC_PAYLOAD_FIELDS
    v=dict(popularity_users=1,dynamics_28d_pct=None,dynamics_7d_pct=Decimal('-2'),cart_add_users=1,market_cart_conversion_pct=Decimal('2.480'),unique_buyers_with_orders=1,market_order_conversion_pct=Decimal('1'),ordered_revenue_rub=Decimal('0'),no_action_queries=1,no_action_share_pct=Decimal('120'))
    assert query_metric_payload_sha256(v)==query_metric_payload_sha256({**v,'market_cart_conversion_pct':Decimal('2.48')})

def test_synthetic_package_mutations():
    data=build_ozon_query_metrics_workbook(raw_numeric_overrides={'B5':'1234.5678'},dimension_ref='A1',horizontal_capitalized=True)
    with ZipFile(BytesIO(data)) as z:
        xml=z.read('xl/worksheets/sheet1.xml')
        assert b'<dimension ref="A1"' in xml and b'1234.5678' in xml
        assert b'horizontal="Left"' in z.read('xl/styles.xml')

def test_parser_uses_raw_decimal_and_false_dimension(tmp_path):
    from backend.ingestion.ozon_query_metrics_xlsx import parse_ozon_query_metrics_xlsx
    p=tmp_path/'x.part';p.write_bytes(build_ozon_query_metrics_workbook(raw_numeric_overrides={'F5':'0.1612','I5':'1234.5678'},dimension_ref='A1'))
    row=parse_ozon_query_metrics_xlsx(p).rows[0]
    assert row.snapshot_values['market_cart_conversion_pct']==Decimal('16.12')
    assert row.snapshot_values['ordered_revenue_rub']==Decimal('1234.5678')

def test_compatibility_copy_preserves_original(tmp_path):
    import hashlib
    from backend.ingestion.ozon_query_metrics_xlsx_compat import prepare_query_metrics_read_copy
    source=tmp_path/'source.xlsx';target=tmp_path/'target.xlsx';source.write_bytes(build_ozon_query_metrics_workbook(horizontal_capitalized=True));before=hashlib.sha256(source.read_bytes()).hexdigest()
    prepare_query_metrics_read_copy(source,target)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    load_workbook(target).close()

@pytest.mark.parametrize("coordinate,value", [
    ("B5", True), ("B5", False), ("B5", "1"), ("F5", "0.5"),
    ("I5", "text"), ("J5", "#VALUE!"), ("K5", "=1/2"),
])
def test_numeric_metrics_require_native_numeric_cells(tmp_path, coordinate, value):
    from backend.ingestion.ozon_query_metrics_xlsx import parse_ozon_query_metrics_xlsx
    data = build_ozon_query_metrics_workbook(formula_cells={coordinate: value})
    path = tmp_path / "metrics.xlsx"
    path.write_bytes(data)
    report = parse_ozon_query_metrics_xlsx(path)
    assert report.rows == ()
    assert report.rows_seen == 1
    assert len(report.row_errors) == 1

@pytest.mark.parametrize("coordinate", ["C5", "D5"])
def test_dynamics_accept_only_numeric_or_exact_dash(tmp_path, coordinate):
    from backend.ingestion.ozon_query_metrics_xlsx import parse_ozon_query_metrics_xlsx
    path = tmp_path / "metrics.xlsx"
    path.write_bytes(build_ozon_query_metrics_workbook(formula_cells={coordinate: "0.5"}))
    assert parse_ozon_query_metrics_xlsx(path).rows == ()

def test_no_action_share_has_no_upper_bound(tmp_path):
    from backend.ingestion.ozon_query_metrics_xlsx import parse_ozon_query_metrics_xlsx
    path = tmp_path / "metrics.xlsx"
    path.write_bytes(build_ozon_query_metrics_workbook(raw_numeric_overrides={"K5": "1.2"}))
    assert parse_ozon_query_metrics_xlsx(path).rows[0].snapshot_values["no_action_share_pct"] == Decimal("120")
