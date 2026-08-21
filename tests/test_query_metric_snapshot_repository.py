from datetime import date, datetime, timezone
from decimal import Decimal
from backend.persistence.database import initialize_database
from backend.persistence.connection import connect
from backend.persistence.repositories.lineage import LineageRepository
from backend.persistence.repositories.search_dimensions import SearchDimensionRepository
from backend.persistence.repositories.query_metric_snapshots import QueryMetricSnapshotRepository
from backend.domain.product_snapshot import SnapshotWriteKind
import pytest

def _case(tmp_path):
 p=tmp_path/'matrix.db';initialize_database(p);c=connect(p);lin=LineageRepository(c);b=lin.create_import_batch(source='ozon',import_kind='test');a=lin.add_source_artifact(b.id,artifact_kind='test',original_name='x',content_sha256='a'*64,byte_size=1);q=SearchDimensionRepository(c).resolve_search_query('q')
 v=dict(popularity_users=0,dynamics_28d_pct=None,dynamics_7d_pct=Decimal('-999999'),cart_add_users=0,market_cart_conversion_pct=Decimal('0'),unique_buyers_with_orders=0,market_order_conversion_pct=Decimal('100'),ordered_revenue_rub=Decimal('0'),no_action_queries=0,no_action_share_pct=Decimal('120'))
 kw=dict(search_query_id=q.id,period_start=date(2026,1,1),period_end=date(2026,1,2),payload_sha256='b'*64,import_batch_id=b.id,source_artifact_id=a.id,imported_at=datetime.now(timezone.utc),snapshot_values=v)
 return c,QueryMetricSnapshotRepository(c),kw

@pytest.mark.parametrize('mutation',[{'period_start':date(2026,2,1)},{'imported_at':datetime(2026,1,1)},{'payload_sha256':'x'},{'snapshot_values':{'missing':1}}])
def test_structural_rejections(tmp_path,mutation):
 c,r,kw=_case(tmp_path);kw.update(mutation)
 with pytest.raises(ValueError):r.resolve_revision(**kw)
 c.close()

@pytest.mark.parametrize('field,value',[
 *[(f,-1) for f in ('popularity_users','cart_add_users','unique_buyers_with_orders','no_action_queries')],
 ('market_cart_conversion_pct',Decimal('-1')),('market_cart_conversion_pct',Decimal('101')),('market_order_conversion_pct',Decimal('-1')),('market_order_conversion_pct',Decimal('101')),('ordered_revenue_rub',Decimal('-1')),('no_action_share_pct',Decimal('-1')),
 *[(f,Decimal(v)) for f in ('dynamics_28d_pct','dynamics_7d_pct','market_cart_conversion_pct','market_order_conversion_pct','ordered_revenue_rub','no_action_share_pct') for v in ('NaN','Infinity','-Infinity')],
])
def test_metric_rejections(tmp_path,field,value):
 c,r,kw=_case(tmp_path);kw['snapshot_values']={**kw['snapshot_values'],field:value}
 with pytest.raises(ValueError):r.resolve_revision(**kw)
 c.close()

def test_valid_extremes_and_period_is_independent(tmp_path):
 c,r,kw=_case(tmp_path);a=r.resolve_revision(**kw);kw['snapshot_values']={**kw['snapshot_values'],'dynamics_28d_pct':Decimal('999999')};kw['payload_sha256']='c'*64;b=r.resolve_revision(**kw);kw['period_start']=kw['period_end']=date(2026,2,1);d=r.resolve_revision(**kw)
 assert (a.kind,b.kind,d.kind)==(SnapshotWriteKind.NEW,SnapshotWriteKind.CORRECTED,SnapshotWriteKind.NEW) and d.snapshot.revision==1;c.close()

def test_revisions_exact_values(tmp_path):
 p=tmp_path/'x.db';initialize_database(p);c=connect(p);lin=LineageRepository(c);b=lin.create_import_batch(source='ozon',import_kind='test');a=lin.add_source_artifact(b.id,artifact_kind='test',original_name='x',content_sha256='a'*64,byte_size=1);q=SearchDimensionRepository(c).resolve_search_query('123');r=QueryMetricSnapshotRepository(c)
 v=dict(popularity_users=1,dynamics_28d_pct=None,dynamics_7d_pct=Decimal('-999999'),cart_add_users=0,market_cart_conversion_pct=Decimal('0'),unique_buyers_with_orders=0,market_order_conversion_pct=Decimal('100'),ordered_revenue_rub=Decimal('0'),no_action_queries=3,no_action_share_pct=Decimal('120.1234'))
 kw=dict(search_query_id=q.id,period_start=date(2026,1,1),period_end=date(2026,1,2),payload_sha256='b'*64,import_batch_id=b.id,source_artifact_id=a.id,imported_at=datetime.now(timezone.utc),snapshot_values=v)
 x=r.resolve_revision(**kw);assert x.kind is SnapshotWriteKind.NEW and x.snapshot.no_action_share_pct==Decimal('120.1234');assert r.resolve_revision(**kw).kind is SnapshotWriteKind.DUPLICATE
 kw['payload_sha256']='c'*64;kw['snapshot_values']={**v,'popularity_users':2};assert r.resolve_revision(**kw).kind is SnapshotWriteKind.CORRECTED;c.close()
