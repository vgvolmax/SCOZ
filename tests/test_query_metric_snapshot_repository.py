from datetime import date, datetime, timezone
from decimal import Decimal
from backend.persistence.database import initialize_database
from backend.persistence.connection import connect
from backend.persistence.repositories.lineage import LineageRepository
from backend.persistence.repositories.search_dimensions import SearchDimensionRepository
from backend.persistence.repositories.query_metric_snapshots import QueryMetricSnapshotRepository
from backend.domain.product_snapshot import SnapshotWriteKind

def test_revisions_exact_values(tmp_path):
 p=tmp_path/'x.db';initialize_database(p);c=connect(p);lin=LineageRepository(c);b=lin.create_import_batch(source='ozon',import_kind='test');a=lin.add_source_artifact(b.id,artifact_kind='test',original_name='x',content_sha256='a'*64,byte_size=1);q=SearchDimensionRepository(c).resolve_search_query('123');r=QueryMetricSnapshotRepository(c)
 v=dict(popularity_users=1,dynamics_28d_pct=None,dynamics_7d_pct=Decimal('-999999'),cart_add_users=0,market_cart_conversion_pct=Decimal('0'),unique_buyers_with_orders=0,market_order_conversion_pct=Decimal('100'),ordered_revenue_rub=Decimal('0'),no_action_queries=3,no_action_share_pct=Decimal('120.1234'))
 kw=dict(search_query_id=q.id,period_start=date(2026,1,1),period_end=date(2026,1,2),payload_sha256='b'*64,import_batch_id=b.id,source_artifact_id=a.id,imported_at=datetime.now(timezone.utc),snapshot_values=v)
 x=r.resolve_revision(**kw);assert x.kind is SnapshotWriteKind.NEW and x.snapshot.no_action_share_pct==Decimal('120.1234');assert r.resolve_revision(**kw).kind is SnapshotWriteKind.DUPLICATE
 kw['payload_sha256']='c'*64;kw['snapshot_values']={**v,'popularity_users':2};assert r.resolve_revision(**kw).kind is SnapshotWriteKind.CORRECTED;c.close()
