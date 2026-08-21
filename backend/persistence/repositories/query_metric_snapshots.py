import re, sqlite3
from datetime import date, datetime
from decimal import Decimal
from typing import Mapping
from backend.domain.lineage import datetime_from_db, datetime_to_db
from backend.domain.product_snapshot import SnapshotWriteKind, canonical_decimal_text
from backend.domain.query_metric import QUERY_METRIC_PAYLOAD_FIELDS, QueryMetricSnapshot, QueryMetricWriteResult
_DECIMALS={'dynamics_28d_pct','dynamics_7d_pct','market_cart_conversion_pct','market_order_conversion_pct','ordered_revenue_rub','no_action_share_pct'}
class QueryMetricSnapshotRepository:
 def __init__(self,conn):self._conn=conn
 def get(self,snapshot_id):
  r=self._conn.execute('SELECT * FROM query_metric_snapshots WHERE id=?',(snapshot_id,)).fetchone();return None if r is None else self._map(r)
 def find_current(self,*,search_query_id,period_start,period_end):
  r=self._conn.execute('SELECT * FROM query_metric_snapshots WHERE search_query_id=? AND period_start=? AND period_end=? ORDER BY revision DESC LIMIT 1',(search_query_id,period_start.isoformat(),period_end.isoformat())).fetchone();return None if r is None else self._map(r)
 def resolve_revision(self,*,search_query_id:int,period_start:date,period_end:date,payload_sha256:str,import_batch_id:int,source_artifact_id:int,imported_at:datetime,snapshot_values:Mapping[str,object]):
  self._validate(period_start,period_end,payload_sha256,imported_at,snapshot_values); current=self.find_current(search_query_id=search_query_id,period_start=period_start,period_end=period_end)
  if current and current.payload_sha256==payload_sha256:return QueryMetricWriteResult(SnapshotWriteKind.DUPLICATE,current)
  rev=1 if current is None else current.revision+1; sup=None if current is None else current.id;vals=[canonical_decimal_text(v) if isinstance(v,Decimal) else v for v in (snapshot_values[n] for n in QUERY_METRIC_PAYLOAD_FIELDS)];cols=','.join(QUERY_METRIC_PAYLOAD_FIELDS);marks=','.join('?' for _ in range(8+len(vals)))
  c=self._conn.execute(f'INSERT INTO query_metric_snapshots(search_query_id,period_start,period_end,revision,supersedes_snapshot_id,payload_sha256,import_batch_id,source_artifact_id,imported_at,{cols}) VALUES (?,{marks})',(search_query_id,period_start.isoformat(),period_end.isoformat(),rev,sup,payload_sha256,import_batch_id,source_artifact_id,datetime_to_db(imported_at),*vals));return QueryMetricWriteResult(SnapshotWriteKind.NEW if current is None else SnapshotWriteKind.CORRECTED,self.get(c.lastrowid))
 @staticmethod
 def _validate(start,end,sha,imported,v):
  if start>end:raise ValueError('period start must not exceed end')
  if not re.fullmatch('[0-9a-f]{64}',sha):raise ValueError('invalid payload hash')
  datetime_to_db(imported)
  if set(v)!=set(QUERY_METRIC_PAYLOAD_FIELDS):raise ValueError('snapshot payload fields do not match frozen contract')
  for n in ('popularity_users','cart_add_users','unique_buyers_with_orders','no_action_queries'):
   if isinstance(v[n],bool) or not isinstance(v[n],int) or v[n]<0:raise ValueError(f'invalid {n}')
  for n in _DECIMALS:
   x=v[n]
   if x is None and n.startswith('dynamics_'):continue
   if not isinstance(x,Decimal) or not x.is_finite():raise ValueError(f'invalid {n}')
  if not 0<=v['market_cart_conversion_pct']<=100 or not 0<=v['market_order_conversion_pct']<=100 or v['ordered_revenue_rub']<0 or v['no_action_share_pct']<0:raise ValueError('decimal out of bounds')
 @staticmethod
 def _map(row):
  v=dict(row);v['period_start']=date.fromisoformat(v['period_start']);v['period_end']=date.fromisoformat(v['period_end']);v['imported_at']=datetime_from_db(v['imported_at'])
  for n in _DECIMALS:
   if v[n] is not None:v[n]=Decimal(v[n])
  return QueryMetricSnapshot(**v)
