from fastapi.testclient import TestClient
import pytest
import backend.main as main
import backend.application.ozon_query_metrics_import as service
from backend.application.import_runtime import IMPORT_LOCK
from backend.persistence.database import initialize_database
from tests.xlsx_factory import OZON_QUERY_METRICS_HEADERS as H,build_ozon_products_workbook,build_ozon_query_metrics_workbook
MEDIA='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
def _client(monkeypatch,tmp_path):
 db=tmp_path/'scoz.db';initialize_database(db);monkeypatch.setenv('SCOZ_DB_PATH',str(db));monkeypatch.setattr(main,'DATA_DIR',tmp_path);return TestClient(main.app)
def _post(c,p,name='metrics.xlsx'):return c.post('/api/imports/ozon-query-metrics',files={'file':(name,p,MEDIA)})
def _row(q='q',**x):
 r=dict(zip(H,(q,1,'-',0,1,0,1,1,1,0,0),strict=True));r.update(x);return r
def test_real_http_success_exact_context_and_no_generated_at(monkeypatch,tmp_path):
 with _client(monkeypatch,tmp_path) as c:r=_post(c,build_ozon_query_metrics_workbook())
 b=r.json();assert r.status_code==200 and b['report_type']=='OZON_QUERY_METRICS' and b['status']=='SUCCESS'
 assert (b['period_start'],b['period_end'],b['sort_context'])==('2026-07-21','2026-08-17','Сортировка: По убыванию в Популярность запроса')
 assert 'generated_at' not in b and (tmp_path/b['source_artifact']['stored_relpath']).is_file()
def test_partial_truncates_errors(monkeypatch,tmp_path):
 rows=(_row(),)+tuple(_row(str(i),**{H[1]:-1}) for i in range(52))
 with _client(monkeypatch,tmp_path) as c:r=_post(c,build_ozon_query_metrics_workbook(rows=rows))
 b=r.json();assert r.status_code==200 and b['status']=='PARTIAL_SUCCESS' and b['row_errors_total']==52 and len(b['row_errors'])==50 and b['row_errors_truncated']
@pytest.mark.parametrize('payload,code',[(b'bad secret','UNSUPPORTED_WORKBOOK'),(build_ozon_products_workbook(),'WRONG_REPORT_TYPE'),(build_ozon_query_metrics_workbook(headers=('bad',*H[1:])),'INCOMPATIBLE_REPORT_SCHEMA'),(build_ozon_query_metrics_workbook(period='bad'),'INVALID_REPORT_PERIOD'),(build_ozon_query_metrics_workbook(rows=(_row(),_row(**{H[1]:2}))),'CONFLICTING_OBSERVATION_ROWS'),(build_ozon_query_metrics_workbook(rows=(_row(**{H[1]:-1}),)),'NO_USABLE_ROWS')])
def test_http_error_matrix_sanitized(monkeypatch,tmp_path,payload,code):
 with _client(monkeypatch,tmp_path) as c:r=_post(c,payload)
 assert r.status_code==422 and r.json()['error']['code']==code and r.json()['result']['status']=='FAILED'
 assert all(x not in r.text for x in ('Traceback','/tmp/','.part','.readcopy','secret','SQL'))
def test_transport_lock_and_size(monkeypatch,tmp_path):
 with _client(monkeypatch,tmp_path) as c:
  wrong=c.post('/api/imports/ozon-query-metrics',content=b'x');ext=_post(c,b'x','x.xls');missing=c.post('/api/imports/ozon-query-metrics');field=c.post('/api/imports/ozon-query-metrics',files={'wrong':('x.xlsx',b'x')})
  IMPORT_LOCK.acquire()
  try:locked=_post(c,build_ozon_query_metrics_workbook())
  finally:IMPORT_LOCK.release()
  monkeypatch.setattr(service,'MAX_UPLOAD_BYTES',4);large=_post(c,b'12345')
 assert wrong.status_code==ext.status_code==415 and missing.status_code==field.status_code==422 and locked.status_code==409 and large.status_code==413
