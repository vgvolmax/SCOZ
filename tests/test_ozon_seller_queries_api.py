from fastapi.testclient import TestClient
import pytest

import backend.main as main
import backend.application.ozon_seller_queries_import as service
from backend.application.import_runtime import IMPORT_LOCK
from backend.persistence.database import initialize_database
from tests.xlsx_factory import (OZON_SELLER_QUERIES_HEADERS as H,
    build_ozon_products_workbook, build_ozon_seller_queries_workbook)

MEDIA="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

def _client(monkeypatch,tmp_path):
    db=tmp_path/'scoz.db';initialize_database(db);monkeypatch.setenv('SCOZ_DB_PATH',str(db));monkeypatch.setattr(main,'DATA_DIR',tmp_path);return TestClient(main.app)

def _post(client,payload,filename='seller.xlsx'):
    return client.post('/api/imports/ozon-seller-queries',files={'file':(filename,payload,MEDIA)})

def _row(query='q',**changes):
    row=dict(zip(H[3:],(query,'1','2','1','10%','2%','0','0 ₽'),strict=True));row.update(changes);return row

def test_real_http_success_contract(monkeypatch,tmp_path):
    with _client(monkeypatch,tmp_path) as client:r=_post(client,build_ozon_seller_queries_workbook())
    assert r.status_code==200;b=r.json();assert b['report_type']=='OZON_OWN_PRODUCT_QUERIES' and b['status']=='SUCCESS'
    assert (b['generated_at'],b['period_start'],b['period_end'],b['product_ozon_id'])==('2026-08-18T04:10:00+00:00','2026-07-20','2026-08-17','100000001')
    assert (b['rows_seen'],b['rows_accepted'],b['rows_skipped'],b['new_observations'])==(1,1,0,1)
    assert 'rows' not in b and (tmp_path/b['source_artifact']['stored_relpath']).is_file()

def test_partial_and_error_truncation(monkeypatch,tmp_path):
    rows=(_row(),)+tuple(_row(str(i),**{H[6]:'bad'}) for i in range(52))
    with _client(monkeypatch,tmp_path) as client:r=_post(client,build_ozon_seller_queries_workbook(rows=rows))
    b=r.json();assert r.status_code==200 and b['status']=='PARTIAL_SUCCESS';assert b['row_errors_total']==52 and len(b['row_errors'])==50 and b['row_errors_truncated'] is True

@pytest.mark.parametrize('payload,code',[
    (b'not xlsx secret','UNSUPPORTED_WORKBOOK'),(build_ozon_products_workbook(),'WRONG_REPORT_TYPE'),
    (build_ozon_seller_queries_workbook(headers=('bad',*H[1:])),'INCOMPATIBLE_REPORT_SCHEMA'),
    (build_ozon_seller_queries_workbook(date='bad'),'INVALID_GENERATED_AT'),
    (build_ozon_seller_queries_workbook(period_start='bad'),'INVALID_REPORT_PERIOD'),
    (build_ozon_seller_queries_workbook(ozon_id=0),'INVALID_PRODUCT_CONTEXT'),
    (build_ozon_seller_queries_workbook(rows=(_row(),_row(**{H[5]:'3'}))),'CONFLICTING_OBSERVATION_ROWS'),
    (build_ozon_seller_queries_workbook(rows=(_row(**{H[6]:'bad'}),)),'NO_USABLE_ROWS'),
])
def test_real_http_parser_error_envelopes_are_sanitized(monkeypatch,tmp_path,payload,code):
    with _client(monkeypatch,tmp_path) as client:r=_post(client,payload)
    assert r.status_code==422 and r.json()['error']['code']==code and r.json()['result']['status']=='FAILED'
    assert all(x not in r.text for x in ('Traceback','/tmp/','.part','.readcopy','secret','SQL'))

def test_transport_lock_and_size_matrix(monkeypatch,tmp_path):
    with _client(monkeypatch,tmp_path) as client:
        wrong_type=client.post('/api/imports/ozon-seller-queries',content=b'x');wrong_ext=_post(client,b'x','x.xls')
        missing=client.post('/api/imports/ozon-seller-queries');wrong_field=client.post('/api/imports/ozon-seller-queries',files={'wrong':('x.xlsx',b'x')})
        IMPORT_LOCK.acquire()
        try: locked=_post(client,build_ozon_seller_queries_workbook())
        finally: IMPORT_LOCK.release()
        monkeypatch.setattr(service,'MAX_UPLOAD_BYTES',4);large=_post(client,b'12345')
    assert wrong_type.status_code==wrong_ext.status_code==415;assert missing.status_code==wrong_field.status_code==422
    assert locked.status_code==409 and locked.json()['result'] is None;assert large.status_code==413 and large.json()['result'] is None

def test_expected_persistence_failure_is_500_and_sanitized(monkeypatch,tmp_path):
    from backend.persistence.repositories.search_dimensions import SearchDimensionRepository
    monkeypatch.setattr(SearchDimensionRepository,'resolve_search_query',lambda *a,**k:(_ for _ in ()).throw(Exception('programming-test-sentinel')))
    with _client(monkeypatch,tmp_path) as client:r=_post(client,build_ozon_seller_queries_workbook())
    assert r.status_code==500 and r.json()['error']['code']=='IMPORT_PERSISTENCE_ERROR' and 'sentinel' not in r.text
