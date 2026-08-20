import re, sqlite3
from datetime import date, datetime
from decimal import Decimal
from typing import Mapping
from backend.domain.lineage import datetime_from_db, datetime_to_db
from backend.domain.product_snapshot import SnapshotWriteKind, canonical_decimal_text
from backend.domain.product_query import PRODUCT_QUERY_PAYLOAD_FIELDS, ProductQueryPositionState, ProductQuerySnapshot, ProductQueryWriteResult

_DECIMALS={'search_to_card_conversion_pct','search_to_order_conversion_pct','ordered_revenue_rub'}
class ProductQuerySnapshotRepository:
 def __init__(self, conn): self._conn=conn
 def get(self,snapshot_id):
  r=self._conn.execute('SELECT * FROM product_query_snapshots WHERE id=?',(snapshot_id,)).fetchone(); return None if r is None else self._map(r)
 def find_current(self,*,product_id,search_query_id,period_start,period_end):
  r=self._conn.execute('SELECT * FROM product_query_snapshots WHERE product_id=? AND search_query_id=? AND period_start=? AND period_end=? ORDER BY revision DESC LIMIT 1',(product_id,search_query_id,period_start.isoformat(),period_end.isoformat())).fetchone(); return None if r is None else self._map(r)
 def resolve_revision(self,*,product_id:int,search_query_id:int,period_start:date,period_end:date,payload_sha256:str,import_batch_id:int,source_artifact_id:int,imported_at:datetime,snapshot_values:Mapping[str,object]):
  self._validate(period_start,period_end,payload_sha256,imported_at,snapshot_values)
  current=self.find_current(product_id=product_id,search_query_id=search_query_id,period_start=period_start,period_end=period_end)
  if current and current.payload_sha256==payload_sha256:return ProductQueryWriteResult(SnapshotWriteKind.DUPLICATE,current)
  revision=1 if current is None else current.revision+1; supersedes=None if current is None else current.id
  vals=[self._encode(n,snapshot_values[n]) for n in PRODUCT_QUERY_PAYLOAD_FIELDS]
  cols=','.join(PRODUCT_QUERY_PAYLOAD_FIELDS); marks=','.join('?' for _ in range(9+len(vals)))
  c=self._conn.execute(f'INSERT INTO product_query_snapshots(product_id,search_query_id,period_start,period_end,revision,supersedes_snapshot_id,payload_sha256,import_batch_id,source_artifact_id,imported_at,{cols}) VALUES (?,{marks})',(product_id,search_query_id,period_start.isoformat(),period_end.isoformat(),revision,supersedes,payload_sha256,import_batch_id,source_artifact_id,datetime_to_db(imported_at),*vals))
  return ProductQueryWriteResult(SnapshotWriteKind.NEW if current is None else SnapshotWriteKind.CORRECTED,self.get(c.lastrowid))
 @staticmethod
 def _validate(start,end,sha,imported,values):
  if start>end: raise ValueError('period start must not exceed end')
  if not re.fullmatch('[0-9a-f]{64}',sha): raise ValueError('invalid payload hash')
  datetime_to_db(imported)
  if set(values)!=set(PRODUCT_QUERY_PAYLOAD_FIELDS):raise ValueError('snapshot payload fields do not match frozen contract')
  for n in ('searched_users','seen_users','ordered_units'):
   if isinstance(values[n],bool) or not isinstance(values[n],int) or values[n]<0:raise ValueError(f'invalid {n}')
  state=values['position_state']; pos=values['average_position']
  if state==ProductQueryPositionState.KNOWN:
   if isinstance(pos,bool) or not isinstance(pos,int) or pos<=0:raise ValueError('invalid position')
  elif state!=ProductQueryPositionState.SOURCE_ZERO or pos is not None:raise ValueError('invalid position state')
  for n in _DECIMALS:
   v=values[n]
   if not isinstance(v,Decimal) or not v.is_finite():raise ValueError(f'invalid {n}')
  if not 0<=values['search_to_card_conversion_pct']<=100 or not 0<=values['search_to_order_conversion_pct']<=100 or values['ordered_revenue_rub']<0:raise ValueError('decimal out of bounds')
 @staticmethod
 def _encode(n,v):
  if isinstance(v,Decimal):return canonical_decimal_text(v)
  if isinstance(v,ProductQueryPositionState):return v.value
  return v
 @staticmethod
 def _map(row):
  v=dict(row); v['period_start']=date.fromisoformat(v['period_start']);v['period_end']=date.fromisoformat(v['period_end']);v['imported_at']=datetime_from_db(v['imported_at']);v['position_state']=ProductQueryPositionState(v['position_state'])
  for n in _DECIMALS:v[n]=Decimal(v[n])
  return ProductQuerySnapshot(**v)
