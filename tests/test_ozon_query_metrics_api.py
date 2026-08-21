import sqlite3

from fastapi.testclient import TestClient
import pytest
import backend.main as main
import backend.application.import_runtime as import_runtime
from backend.application.import_runtime import ARCHIVE_RE, IMPORT_LOCK
from backend.domain.lineage import ImportStatus
from backend.persistence.connection import connect, transaction
from backend.persistence.database import initialize_database
from backend.persistence.repositories.lineage import LineageRepository
from backend.persistence.repositories.search_dimensions import SearchDimensionRepository
from tests.xlsx_factory import (OZON_QUERY_METRICS_HEADERS as H,
 build_ozon_products_workbook,build_ozon_query_metrics_workbook,
 build_ozon_search_visibility_workbook,build_ozon_seller_queries_workbook)
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
  wrong=c.post('/api/imports/ozon-query-metrics',content=b'x');ext=_post(c,b'x','x.xls')
  missing = c.post(
      "/api/imports/ozon-query-metrics",
      content=b"--empty--\r\n--empty----\r\n",
      headers={"content-type": "multipart/form-data; boundary=empty"},
  )
  field=c.post('/api/imports/ozon-query-metrics',files={'wrong':('x.xlsx',b'x')})
  IMPORT_LOCK.acquire()
  try:locked=_post(c,build_ozon_query_metrics_workbook())
  finally:IMPORT_LOCK.release()
  monkeypatch.setattr(import_runtime,'MAX_UPLOAD_BYTES',4);large=_post(c,b'12345')
 assert wrong.status_code==ext.status_code==415 and missing.status_code==field.status_code==422 and locked.status_code==409
 assert large.status_code==413 and large.json()['error']['code']=='UPLOAD_TOO_LARGE' and large.json()['result'] is None
 with connect(tmp_path/'scoz.db') as conn:assert LineageRepository(conn).count_import_history()==0
 imports=tmp_path/'imports';assert not list(imports.glob('.upload-*')) and not list(imports.glob('*.xlsx'))

def test_expected_persistence_failure_is_500_compensated_and_sanitized(monkeypatch,tmp_path):
 def raise_persistence_error(*args,**kwargs):raise sqlite3.OperationalError('persistence-test-sentinel')
 monkeypatch.setattr(SearchDimensionRepository,'resolve_search_query',raise_persistence_error)
 with _client(monkeypatch,tmp_path) as c:r=_post(c,build_ozon_query_metrics_workbook())
 assert r.status_code==500 and r.json()['error']['code']=='IMPORT_PERSISTENCE_ERROR'
 assert r.json()['result']['status']=='FAILED'
 assert all(value not in r.text for value in ('persistence-test-sentinel','Traceback','.part','.readcopy'))
 assert 'sqlite' not in r.text.lower()
 with connect(tmp_path/'scoz.db') as conn:
  for table in ('search_queries','query_metric_snapshots','products','clusters'):
   assert conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]==0
  assert conn.execute("SELECT status FROM import_batches WHERE import_kind='ozon_query_metrics_xlsx'").fetchone()['status']=='FAILED'
 imports=tmp_path/'imports'
 assert not list(imports.glob('.upload-*')) and not list(imports.glob('.readcopy-*')) and not list(imports.glob('*.xlsx'))
 assert not IMPORT_LOCK.locked()

@pytest.mark.parametrize(('payload','filename','expected_status'),[
 (build_ozon_query_metrics_workbook(),'metrics-success.xlsx',200),
 (b'not an xlsx','metrics-malformed.xlsx',422),
])
def test_route_closes_upload_file_on_success_and_handled_failure(monkeypatch,tmp_path,payload,filename,expected_status):
 original_close=main.UploadFile.close;closed=[]
 async def tracked_close(self):
  closed.append(self.filename);await original_close(self)
 monkeypatch.setattr(main.UploadFile,'close',tracked_close)
 with _client(monkeypatch,tmp_path) as c:r=_post(c,payload,filename)
 assert r.status_code==expected_status and filename in closed

def test_import_history_contains_all_four_report_types_and_context(monkeypatch,tmp_path):
 with _client(monkeypatch,tmp_path) as c:
  assert c.post('/api/imports/ozon-products',files={'file':('products.xlsx',build_ozon_products_workbook(),MEDIA)}).status_code==200
  assert c.post('/api/imports/ozon-search-visibility',files={'file':('visibility.xlsx',build_ozon_search_visibility_workbook(),MEDIA)}).status_code==200
  assert c.post('/api/imports/ozon-seller-queries',files={'file':('seller.xlsx',build_ozon_seller_queries_workbook(),MEDIA)}).status_code==200
  assert _post(c,build_ozon_query_metrics_workbook()).status_code==200
  body=c.get('/api/imports?limit=10&offset=0').json()
  page=c.get('/api/imports?limit=1&offset=1').json()
 assert body['total']==4
 expected=['OZON_QUERY_METRICS','OZON_OWN_PRODUCT_QUERIES','OZON_SEARCH_VISIBILITY','OZON_PRODUCTS']
 assert [item['report_type'] for item in body['items']]==expected
 by_type={item['report_type']:item for item in body['items']}
 products=by_type['OZON_PRODUCTS'];assert products['report_generated_on'] and products['report_window_days']
 assert products['report_generated_at'] is products['sort_context'] is products['report_product_ozon_id'] is None
 visibility=by_type['OZON_SEARCH_VISIBILITY'];assert visibility['observed_at'] and visibility['query_text'] and visibility['cluster_name']
 seller=by_type['OZON_OWN_PRODUCT_QUERIES'];assert seller['report_generated_at'] and seller['period_start'] and seller['period_end'] and seller['report_product_ozon_id']
 assert seller['sort_context'] is None
 metrics=by_type['OZON_QUERY_METRICS'];assert metrics['period_start'] and metrics['period_end']
 assert metrics['sort_context']=='Сортировка: По убыванию в Популярность запроса'
 assert metrics['report_generated_at'] is None and metrics['report_product_ozon_id'] is None
 assert page['total']==4 and len(page['items'])==1

def _finish_failed_pr5(repo,kind):
 batch=repo.create_import_batch(source='ozon',import_kind=kind)
 common=dict(status=ImportStatus.FAILED,period_start=None,period_end=None,rows_seen=0,rows_accepted=0,rows_skipped=0,duplicate_observations=0,new_observations=0,corrected_revisions=0,warnings_count=0,row_errors_total=0)
 if kind=='ozon_seller_queries_xlsx':repo.finish_ozon_seller_queries_import(batch.id,generated_at=None,product_ozon_id=None,**common)
 else:repo.finish_ozon_query_metrics_import(batch.id,sort_context=None,**common)

def test_source_availability_is_independent_of_history_page(monkeypatch,tmp_path):
 with _client(monkeypatch,tmp_path) as c:
  seller=c.post('/api/imports/ozon-seller-queries',files={'file':('seller.xlsx',build_ozon_seller_queries_workbook(),MEDIA)}).json()['import_batch_id']
  metrics=_post(c,build_ozon_query_metrics_workbook()).json()['import_batch_id']
  with transaction(tmp_path/'scoz.db') as conn:
   repo=LineageRepository(conn)
   for index in range(55):_finish_failed_pr5(repo,'ozon_seller_queries_xlsx' if index%2==0 else 'ozon_query_metrics_xlsx')
  first=c.get('/api/imports?limit=50&offset=0').json();second=c.get('/api/imports?limit=1&offset=10').json()
 ids={item['import_batch_id'] for item in first['items']}
 assert seller not in ids and metrics not in ids
 expected={'own_product_queries':True,'query_metrics':True}
 assert first['source_availability']==second['source_availability']==expected

def test_lifespan_runs_all_recovery_hooks_and_preserves_referenced_archive(monkeypatch,tmp_path):
 db=tmp_path/'scoz.db';initialize_database(db);imports=tmp_path/'imports';imports.mkdir()
 with transaction(db) as conn:
  repo=LineageRepository(conn)
  seller=repo.create_import_batch(source='ozon',import_kind='ozon_seller_queries_xlsx')
  metrics=repo.create_import_batch(source='ozon',import_kind='ozon_query_metrics_xlsx')
  owner=repo.create_import_batch(source='ozon',import_kind='ozon_products_xlsx')
  archive_name='20260821T000000000000Z-'+'a'*64+'.xlsx';assert ARCHIVE_RE.fullmatch(archive_name)
  repo.add_source_artifact(owner.id,artifact_kind='ozon_products_xlsx',original_name='source.xlsx',content_sha256='a'*64,byte_size=1,stored_relpath=f'imports/{archive_name}')
 stale_upload=imports/'.upload-stale.part';stale_readcopy=imports/'.readcopy-stale.xlsx';archive=imports/archive_name
 stale_upload.write_bytes(b'x');stale_readcopy.write_bytes(b'x');archive.write_bytes(b'x')
 monkeypatch.setenv('SCOZ_DB_PATH',str(db));monkeypatch.setattr(main,'DATA_DIR',tmp_path)
 names=['recover_interrupted_ozon_products_imports','recover_interrupted_ozon_search_visibility_imports','recover_interrupted_ozon_seller_queries_imports','recover_interrupted_ozon_query_metrics_imports'];called=[]
 for name in names:
  original=getattr(main,name)
  def wrapper(*args,_name=name,_original=original,**kwargs):called.append(_name);return _original(*args,**kwargs)
  monkeypatch.setattr(main,name,wrapper)
 with TestClient(main.app):pass
 with connect(db) as conn:
  repo=LineageRepository(conn)
  assert repo.get_import_batch(seller.id).status is ImportStatus.FAILED
  assert repo.get_import_batch(metrics.id).status is ImportStatus.FAILED
 assert not stale_upload.exists() and not stale_readcopy.exists() and archive.exists()
 assert called==names
