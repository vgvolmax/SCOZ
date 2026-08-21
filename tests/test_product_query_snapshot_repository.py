from datetime import date, datetime, timezone
from decimal import Decimal
from backend.persistence.database import initialize_database
from backend.persistence.connection import connect
from backend.persistence.repositories.lineage import LineageRepository
from backend.persistence.repositories.products import ProductRepository
from backend.persistence.repositories.search_dimensions import SearchDimensionRepository
from backend.persistence.repositories.product_query_snapshots import ProductQuerySnapshotRepository
from backend.domain.product_query import ProductQueryPositionState
from backend.domain.product_snapshot import SnapshotWriteKind
import pytest

def _case(tmp_path):
 p=tmp_path/'matrix.db';initialize_database(p);c=connect(p);lin=LineageRepository(c);b=lin.create_import_batch(source='ozon',import_kind='test');a=lin.add_source_artifact(b.id,artifact_kind='test',original_name='x',content_sha256='a'*64,byte_size=1);prod=ProductRepository(c).resolve_or_create_ozon_product('1');q=SearchDimensionRepository(c).resolve_search_query('q')
 values=dict(searched_users=0,seen_users=2,position_state=ProductQueryPositionState.KNOWN,average_position=1,search_to_card_conversion_pct=Decimal('0'),search_to_order_conversion_pct=Decimal('100'),ordered_units=0,ordered_revenue_rub=Decimal('0'))
 kw=dict(product_id=prod.id,search_query_id=q.id,period_start=date(2026,1,1),period_end=date(2026,1,2),payload_sha256='b'*64,import_batch_id=b.id,source_artifact_id=a.id,imported_at=datetime.now(timezone.utc),snapshot_values=values)
 return c,ProductQuerySnapshotRepository(c),kw

@pytest.mark.parametrize('mutation',[
 {'period_start':date(2026,1,3)},{'imported_at':datetime(2026,1,1)},{'payload_sha256':'bad'},
 {'snapshot_values':{'missing':1}},
])
def test_rejects_structural_contract(tmp_path,mutation):
 c,r,kw=_case(tmp_path);kw.update(mutation)
 with pytest.raises(ValueError):r.resolve_revision(**kw)
 c.close()

@pytest.mark.parametrize('field,value',[
 ('searched_users',-1),('seen_users',-1),('ordered_units',-1),
 ('search_to_card_conversion_pct',Decimal('-1')),('search_to_card_conversion_pct',Decimal('101')),
 ('search_to_order_conversion_pct',Decimal('-1')),('search_to_order_conversion_pct',Decimal('101')),
 ('ordered_revenue_rub',Decimal('-1')),
 *[(field,value) for field in ('search_to_card_conversion_pct','search_to_order_conversion_pct','ordered_revenue_rub') for value in map(Decimal,('NaN','Infinity','-Infinity'))],
])
def test_rejects_invalid_metric_values(tmp_path,field,value):
 c,r,kw=_case(tmp_path);kw['snapshot_values']={**kw['snapshot_values'],field:value}
 with pytest.raises(ValueError):r.resolve_revision(**kw)
 c.close()

@pytest.mark.parametrize('state,position',[(ProductQueryPositionState.KNOWN,None),(ProductQueryPositionState.KNOWN,0),(ProductQueryPositionState.KNOWN,-1),(ProductQueryPositionState.SOURCE_ZERO,1)])
def test_position_invariant(tmp_path,state,position):
 c,r,kw=_case(tmp_path);kw['snapshot_values']={**kw['snapshot_values'],'position_state':state,'average_position':position}
 with pytest.raises(ValueError):r.resolve_revision(**kw)
 c.close()

def test_valid_boundaries_and_period_is_independent(tmp_path):
 c,r,kw=_case(tmp_path);first=r.resolve_revision(**kw);kw['period_start']=kw['period_end']=date(2026,2,1);second=r.resolve_revision(**kw)
 assert first.kind is second.kind is SnapshotWriteKind.NEW and first.snapshot.revision==second.snapshot.revision==1;c.close()

def test_revisions_and_roundtrip(tmp_path):
 p=tmp_path/'x.db';initialize_database(p);c=connect(p); lin=LineageRepository(c);b=lin.create_import_batch(source='ozon',import_kind='test');a=lin.add_source_artifact(b.id,artifact_kind='test',original_name='x',content_sha256='a'*64,byte_size=1);prod=ProductRepository(c).resolve_or_create_ozon_product('1');q=SearchDimensionRepository(c).resolve_search_query('q');r=ProductQuerySnapshotRepository(c)
 v=dict(searched_users=2,seen_users=3,position_state=ProductQueryPositionState.KNOWN,average_position=1,search_to_card_conversion_pct=Decimal('2.480'),search_to_order_conversion_pct=Decimal('1'),ordered_units=0,ordered_revenue_rub=Decimal('0'))
 kw=dict(product_id=prod.id,search_query_id=q.id,period_start=date(2026,1,1),period_end=date(2026,1,2),payload_sha256='b'*64,import_batch_id=b.id,source_artifact_id=a.id,imported_at=datetime.now(timezone.utc),snapshot_values=v)
 x=r.resolve_revision(**kw);assert x.kind is SnapshotWriteKind.NEW and x.snapshot.search_to_card_conversion_pct==Decimal('2.48');assert r.resolve_revision(**kw).kind is SnapshotWriteKind.DUPLICATE
 kw['payload_sha256']='c'*64;kw['snapshot_values']={**v,'average_position':2};y=r.resolve_revision(**kw);assert y.kind is SnapshotWriteKind.CORRECTED and y.snapshot.supersedes_snapshot_id==x.snapshot.id;c.close()
