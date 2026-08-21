from dataclasses import fields
from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile
from openpyxl import load_workbook
import pytest
from backend.domain.query_metric import *
from tests.xlsx_factory import build_ozon_query_metrics_workbook, OZON_QUERY_METRICS_HEADERS

H = OZON_QUERY_METRICS_HEADERS

def _parse(tmp_path, **kwargs):
    from backend.ingestion.ozon_query_metrics_xlsx import parse_ozon_query_metrics_xlsx
    p=tmp_path/'matrix.xlsx';p.write_bytes(build_ozon_query_metrics_workbook(**kwargs));return parse_ozon_query_metrics_xlsx(p)

def _row(query="query", **changes):
    row=dict(zip(H,(query,1,"-",0,1,0,1,1,Decimal("1.25"),0,0),strict=True));row.update(changes);return row

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

@pytest.mark.parametrize("mutation", [
    {"extra_sheet":True},{"merged_cells":("A1:B1",)},
    {"headers":("wrong",*H[1:])},{"sort_context":"wrong"},
    {"l_plus_values":{"L5":"business"}},{"formula_cells":{"A1":"=1"}},
])
def test_structural_matrix(tmp_path,mutation):
    from backend.domain.query_metric import QueryMetricsIncompatibleReportSchema
    with pytest.raises(QueryMetricsIncompatibleReportSchema):_parse(tmp_path,**mutation)

def test_false_dimension_capitalized_quirk_and_small_report_are_valid(tmp_path):
    assert len(_parse(tmp_path,dimension_ref="A1").rows)==1
    from backend.ingestion.ozon_query_metrics_xlsx_compat import prepare_query_metrics_read_copy
    source=tmp_path/'capitalized.xlsx';copy=tmp_path/'copy.xlsx'
    source.write_bytes(build_ozon_query_metrics_workbook(horizontal_capitalized=True))
    prepare_query_metrics_read_copy(source,copy)
    from backend.ingestion.ozon_query_metrics_xlsx import parse_ozon_query_metrics_xlsx
    assert len(parse_ozon_query_metrics_xlsx(copy).rows)==1

@pytest.mark.parametrize("factory", [
    pytest.param(lambda: __import__('tests.xlsx_factory',fromlist=['build_ozon_products_workbook']).build_ozon_products_workbook(),id='products'),
    pytest.param(lambda: __import__('tests.xlsx_factory',fromlist=['build_ozon_search_visibility_workbook']).build_ozon_search_visibility_workbook(),id='visibility'),
    pytest.param(lambda: __import__('tests.xlsx_factory',fromlist=['build_ozon_seller_queries_workbook']).build_ozon_seller_queries_workbook(),id='seller'),
])
def test_foreign_report_classification(tmp_path,factory):
    from backend.domain.query_metric import QueryMetricsWrongReportType
    from backend.ingestion.ozon_query_metrics_xlsx import parse_ozon_query_metrics_xlsx
    p=tmp_path/'foreign.xlsx';p.write_bytes(factory())
    with pytest.raises(QueryMetricsWrongReportType):parse_ozon_query_metrics_xlsx(p)

@pytest.mark.parametrize("query,expected",[(" query ","query"),("\u00a0q\u00a0","q"),("Two  Words","Two  Words"),("Ёж!","Ёж!"),("001", "001")])
def test_query_identity(tmp_path,query,expected):
    assert _parse(tmp_path,rows=(_row(query),)).rows[0].query_text==expected

@pytest.mark.parametrize("changes,expected",[
    ({H[1]:0},{"popularity_users":0}),({H[1]:999},{"popularity_users":999}),
    ({H[2]:"-",H[3]:"-"},{"dynamics_28d_pct":None,"dynamics_7d_pct":None}),
    ({H[2]:0,H[3]:-999999},{"dynamics_28d_pct":Decimal('0'),"dynamics_7d_pct":Decimal('-99999900')}),
    ({H[5]:0,H[7]:1},{"market_cart_conversion_pct":Decimal('0'),"market_order_conversion_pct":Decimal('100')}),
    ({H[8]:Decimal('1234.5678')},{"ordered_revenue_rub":Decimal('1234.5678')}),
    ({H[10]:0},{"no_action_share_pct":Decimal('0')}),({H[10]:1.2},{"no_action_share_pct":Decimal('120')}),
])
def test_numeric_valid_boundaries(tmp_path,changes,expected):
    values=_parse(tmp_path,rows=(_row(**changes),)).rows[0].snapshot_values
    assert all(values[k]==v for k,v in expected.items())

@pytest.mark.parametrize("changes",[
    {H[1]:-1},{H[1]:1.5},{H[4]:-1},{H[6]:1.5},{H[9]:-1},
    {H[2]:"unsupported"},{H[5]:-0.1},{H[5]:1.1},{H[8]:-1},{H[10]:-0.1},
])
def test_numeric_invalid_boundaries_are_row_errors(tmp_path,changes):
    report=_parse(tmp_path,rows=(_row(**changes),));assert report.rows==() and len(report.row_errors)==1

def test_duplicate_conflict_and_counter_invariant(tmp_path):
    from backend.domain.query_metric import QueryMetricsConflictingObservationRows
    one=_row('one');report=_parse(tmp_path,rows=(one,_row('two'),_row('bad',**{H[1]:-1}),dict(one)))
    assert report.duplicate_input_rows==1
    assert report.rows_seen==len(report.rows)+len(report.row_errors)+report.duplicate_input_rows
    with pytest.raises(QueryMetricsConflictingObservationRows):_parse(tmp_path,rows=(one,_row('one',**{H[1]:2})))
