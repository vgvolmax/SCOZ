import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.domain.product_snapshot import SnapshotWriteKind
from backend.domain.search_visibility import CpcState, CpoState, SEARCH_VISIBILITY_PAYLOAD_FIELDS
from backend.persistence.connection import connect
from backend.persistence.database import initialize_database
from backend.persistence.repositories.lineage import LineageRepository
from backend.persistence.repositories.products import ProductRepository
from backend.persistence.repositories.search_dimensions import SearchDimensionRepository
from backend.persistence.repositories.search_visibility_snapshots import SearchVisibilitySnapshotRepository


def _values(*, cpc_state=CpcState.ACTIVE, cpo_state=CpoState.ACTIVE, reviews=True, promotion=True, position=1):
    return {
        "source_title": "Title", "seller_name": "Seller", "position": position,
        "overall_score": Decimal("1.2300"), "promotion_status": "Status",
        "cpc_state": cpc_state,
        "cpc_rub": Decimal("10.500") if cpc_state is CpcState.ACTIVE else None,
        "promotion_strategy": "Strategy",
        "cpo_state": cpo_state,
        "cpo_pct": Decimal("5.00") if cpo_state is CpoState.ACTIVE else None,
        "relevance_score": Decimal("99.10"),
        "rating": Decimal("4.80") if reviews else None,
        "reviews_count": 1234 if reviews else None,
        "buyer_price_rub": Decimal("1999.00"),
        "popularity_score": Decimal("42.20"), "ozon_promotion": promotion,
        "delivery_label": "1-2 days", "delivery_min_days": 1,
        "delivery_max_days": 2, "price_index_pct": Decimal("10.00"),
    }


@pytest.fixture
def state(tmp_path):
    db = tmp_path / "scoz.db"
    initialize_database(db)
    conn = connect(db)
    lineage = LineageRepository(conn)
    batch = lineage.create_import_batch(source="ozon", import_kind="ozon_search_visibility_xlsx")
    artifact = lineage.add_source_artifact(
        batch.id, artifact_kind="ozon_search_visibility_xlsx", original_name="x.xlsx",
        content_sha256="a" * 64, byte_size=1,
    )
    product = ProductRepository(conn).resolve_or_create_ozon_product("1")
    dimensions = SearchDimensionRepository(conn)
    query = dimensions.resolve_search_query("query")
    cluster = dimensions.resolve_cluster("cluster")
    try:
        yield conn, SearchVisibilitySnapshotRepository(conn), product.id, query.id, cluster.id, batch.id, artifact.id
    finally:
        conn.close()


def _write(state, *, digest="b" * 64, observed=None, imported=None, values=None,
           product_id=None, query_id=None, cluster_id=None):
    _, repo, product, query, cluster, batch, artifact = state
    return repo.resolve_revision(
        product_id=product if product_id is None else product_id,
        search_query_id=query if query_id is None else query_id,
        cluster_id=cluster if cluster_id is None else cluster_id,
        observed_at=observed or datetime(2026, 8, 17, 3, 55, tzinfo=timezone.utc),
        payload_sha256=digest, import_batch_id=batch, source_artifact_id=artifact,
        imported_at=imported or datetime(2026, 8, 17, 4, tzinfo=timezone.utc),
        snapshot_values=values or _values(),
    )


def test_new_duplicate_correction_and_immutable_revision(state):
    first = _write(state)
    duplicate = _write(state)
    corrected = _write(state, digest="c" * 64, values=_values(position=2))
    assert first.kind is SnapshotWriteKind.NEW and first.snapshot.revision == 1
    assert duplicate.kind is SnapshotWriteKind.DUPLICATE and duplicate.snapshot.id == first.snapshot.id
    assert corrected.kind is SnapshotWriteKind.CORRECTED and corrected.snapshot.revision == 2
    assert corrected.snapshot.supersedes_snapshot_id == first.snapshot.id
    assert state[1].find_current(product_id=state[2], search_query_id=state[3], cluster_id=state[4], observed_at=first.snapshot.observed_at).id == corrected.snapshot.id
    row = state[0].execute("SELECT revision, position FROM search_visibility_snapshots WHERE id=?", (first.snapshot.id,)).fetchone()
    assert tuple(row) == (1, 1)


def test_logical_key_dimensions_are_independent(state):
    _write(state)
    dimensions = SearchDimensionRepository(state[0])
    other_query = dimensions.resolve_search_query("other query")
    other_cluster = dimensions.resolve_cluster("other cluster")
    assert _write(state, query_id=other_query.id).snapshot.revision == 1
    assert _write(state, cluster_id=other_cluster.id).snapshot.revision == 1
    later = datetime(2026, 8, 18, 3, 55, tzinfo=timezone.utc)
    assert _write(state, observed=later).snapshot.revision == 1


@pytest.mark.parametrize("cpo_state", list(CpoState))
@pytest.mark.parametrize("reviews", [True, False])
@pytest.mark.parametrize("promotion", [True, False])
def test_payload_types_decimal_text_and_roundtrip(state, cpo_state, reviews, promotion):
    result = _write(state, values=_values(cpo_state=cpo_state, reviews=reviews, promotion=promotion))
    snapshot = result.snapshot
    assert snapshot.cpo_state is cpo_state
    assert (snapshot.rating, snapshot.reviews_count) == ((Decimal("4.80"), 1234) if reviews else (None, None))
    assert snapshot.ozon_promotion is promotion
    raw = state[0].execute(
        "SELECT overall_score,cpc_rub,buyer_price_rub,ozon_promotion FROM search_visibility_snapshots WHERE id=?",
        (snapshot.id,),
    ).fetchone()
    assert tuple(raw) == ("1.23", "10.5", "1999", int(promotion))

def test_disabled_cpc_roundtrips_as_null_and_is_not_active_zero(state):
    disabled=_write(state,values=_values(cpc_state=CpcState.DISABLED))
    assert disabled.snapshot.cpc_state is CpcState.DISABLED and disabled.snapshot.cpc_rub is None
    assert _values(cpc_state=CpcState.DISABLED) != _values(cpc_state=CpcState.ACTIVE)


@pytest.mark.parametrize("digest", ["A" * 64, "a" * 63, "g" * 64])
def test_invalid_hash_rejected(state, digest):
    with pytest.raises(ValueError, match="invalid payload hash"):
        _write(state, digest=digest)


def test_naive_datetimes_and_payload_shape_rejected(state):
    with pytest.raises(ValueError, match="timezone-aware"):
        _write(state, observed=datetime(2026, 8, 17))
    with pytest.raises(ValueError, match="timezone-aware"):
        _write(state, imported=datetime(2026, 8, 17))
    missing = _values(); missing.pop(SEARCH_VISIBILITY_PAYLOAD_FIELDS[0])
    with pytest.raises(ValueError, match="payload fields"):
        _write(state, values=missing)
    extra = _values(); extra["future"] = 1
    with pytest.raises(ValueError, match="payload fields"):
        _write(state, values=extra)


def test_unique_constraint_defense_and_offset_normalizes_to_utc(state):
    first = _write(
        state,
        observed=datetime(2026, 8, 17, 6, 55, tzinfo=timezone(timedelta(hours=3))),
        imported=datetime(2026, 8, 17, 7, tzinfo=timezone(timedelta(hours=3))),
    )
    assert first.snapshot.observed_at == datetime(2026, 8, 17, 3, 55, tzinfo=timezone.utc)
    assert first.snapshot.imported_at == datetime(2026, 8, 17, 4, tzinfo=timezone.utc)
    columns = [row[1] for row in state[0].execute("PRAGMA table_info(search_visibility_snapshots)")]
    values = list(state[0].execute("SELECT * FROM search_visibility_snapshots WHERE id=?", (first.snapshot.id,)).fetchone())
    with pytest.raises(sqlite3.IntegrityError):
        state[0].execute(
            f"INSERT INTO search_visibility_snapshots ({','.join(columns[1:])}) VALUES ({','.join('?' for _ in columns[1:])})",
            values[1:],
        )
