import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.domain.product_snapshot import SnapshotWriteKind
from backend.domain.search_visibility import (
    CpoState,
    SEARCH_VISIBILITY_PAYLOAD_FIELDS,
    SearchVisibilitySnapshot,
)
from backend.persistence.connection import connect
from backend.persistence.database import initialize_database
from backend.persistence.repositories.lineage import LineageRepository
from backend.persistence.repositories.products import ProductRepository
from backend.persistence.repositories.search_dimensions import SearchDimensionRepository
from backend.persistence.repositories.search_visibility_snapshots import (
    SearchVisibilitySnapshotRepository,
)


def _values(*, position=1, cpo_state=CpoState.ACTIVE, missing_reviews=False):
    return {
        "source_title": "Synthetic product",
        "seller_name": "Synthetic seller",
        "position": position,
        "overall_score": Decimal("1.2300"),
        "promotion_status": "Продвигается",
        "cpc_rub": Decimal("22.30"),
        "promotion_strategy": "Автостратегия",
        "cpo_state": cpo_state,
        "cpo_pct": Decimal("5.00") if cpo_state is CpoState.ACTIVE else None,
        "relevance_score": Decimal("0.500"),
        "rating": None if missing_reviews else Decimal("4.90"),
        "reviews_count": None if missing_reviews else 1200,
        "buyer_price_rub": Decimal("1234.50"),
        "popularity_score": Decimal("7.00"),
        "ozon_promotion": False,
        "delivery_label": "1-2 дня",
        "delivery_min_days": 1,
        "delivery_max_days": 2,
        "price_index_pct": Decimal("99.00"),
    }


@pytest.fixture
def state(tmp_path):
    path = tmp_path / "scoz.db"
    initialize_database(path)
    connection = connect(path)
    lineage = LineageRepository(connection)
    batch = lineage.create_import_batch(source="ozon", import_kind="ozon_search_visibility_xlsx")
    artifact = lineage.add_source_artifact(
        batch.id, artifact_kind="ozon_search_visibility_xlsx", original_name="synthetic.xlsx",
        content_sha256="a" * 64, byte_size=1,
    )
    product = ProductRepository(connection).resolve_or_create_ozon_product("123")
    dimensions = SearchDimensionRepository(connection)
    query = dimensions.resolve_search_query("смеситель")
    cluster = dimensions.resolve_cluster("г. Москва, Россия")
    try:
        yield connection, SearchVisibilitySnapshotRepository(connection), product.id, query.id, cluster.id, batch.id, artifact.id
    finally:
        connection.close()


def _write(state, *, digest="b" * 64, observed_at=None, values=None, query_id=None, cluster_id=None):
    _, repo, product_id, default_query_id, default_cluster_id, batch_id, artifact_id = state
    return repo.resolve_revision(
        product_id=product_id, search_query_id=query_id or default_query_id,
        cluster_id=cluster_id or default_cluster_id,
        observed_at=observed_at or datetime(2026, 8, 17, 3, 55, tzinfo=timezone.utc),
        payload_sha256=digest, import_batch_id=batch_id, source_artifact_id=artifact_id,
        imported_at=datetime(2026, 8, 18, tzinfo=timezone.utc),
        snapshot_values=values or _values(),
    )


def test_new_duplicate_and_corrected_revision_preserve_history(state):
    connection, repo, *_ = state
    first = _write(state)
    original_row = tuple(connection.execute("SELECT * FROM search_visibility_snapshots WHERE id=?", (first.snapshot.id,)).fetchone())
    duplicate = _write(state)
    corrected = _write(state, digest="c" * 64, values=_values(position=2))

    assert first.kind is SnapshotWriteKind.NEW and first.snapshot.revision == 1
    assert duplicate.kind is SnapshotWriteKind.DUPLICATE and duplicate.snapshot == first.snapshot
    assert connection.execute("SELECT count(*) FROM search_visibility_snapshots").fetchone()[0] == 2
    assert corrected.kind is SnapshotWriteKind.CORRECTED and corrected.snapshot.revision == 2
    assert corrected.snapshot.supersedes_snapshot_id == first.snapshot.id
    assert tuple(connection.execute("SELECT * FROM search_visibility_snapshots WHERE id=?", (first.snapshot.id,)).fetchone()) == original_row
    assert repo.find_current(product_id=first.snapshot.product_id, search_query_id=first.snapshot.search_query_id,
        cluster_id=first.snapshot.cluster_id, observed_at=first.snapshot.observed_at) == corrected.snapshot


def test_each_exact_key_dimension_starts_an_independent_revision(state):
    connection, _, _, _, _, _, _ = state
    dimensions = SearchDimensionRepository(connection)
    other_query = dimensions.resolve_search_query("другой запрос")
    other_cluster = dimensions.resolve_cluster("г. Санкт-Петербург, Россия")

    assert _write(state).kind is SnapshotWriteKind.NEW
    assert _write(state, digest="c" * 64, query_id=other_query.id).snapshot.revision == 1
    assert _write(state, digest="d" * 64, cluster_id=other_cluster.id).snapshot.revision == 1
    assert _write(state, digest="e" * 64, observed_at=datetime(2026, 8, 17, 3, 56, tzinfo=timezone.utc)).snapshot.revision == 1


@pytest.mark.parametrize("cpo_state", list(CpoState))
@pytest.mark.parametrize("missing_reviews", [False, True])
def test_round_trip_types_nullable_pairs_and_all_cpo_states(state, cpo_state, missing_reviews):
    connection, *_ = state
    result = _write(state, values=_values(cpo_state=cpo_state, missing_reviews=missing_reviews))
    snapshot = result.snapshot

    assert isinstance(snapshot, SearchVisibilitySnapshot)
    assert snapshot.cpo_state is cpo_state
    assert snapshot.cpo_pct == (Decimal("5") if cpo_state is CpoState.ACTIVE else None)
    assert (snapshot.rating, snapshot.reviews_count) == ((None, None) if missing_reviews else (Decimal("4.9"), 1200))
    assert snapshot.overall_score == Decimal("1.23")
    assert type(snapshot.ozon_promotion) is bool and snapshot.ozon_promotion is False
    raw = connection.execute("SELECT overall_score, ozon_promotion FROM search_visibility_snapshots WHERE id=?", (snapshot.id,)).fetchone()
    assert tuple(raw) == ("1.23", 0)


@pytest.mark.parametrize("digest", ["A" * 64, "a" * 63, "g" * 64])
def test_invalid_hash_is_rejected_before_sql(state, digest):
    connection, *_ = state
    with pytest.raises(ValueError, match="hash"):
        _write(state, digest=digest)
    assert connection.execute("SELECT count(*) FROM search_visibility_snapshots").fetchone()[0] == 0


def test_naive_datetimes_and_wrong_payload_shape_are_rejected_before_sql(state):
    connection, repo, product_id, query_id, cluster_id, batch_id, artifact_id = state
    base = dict(product_id=product_id, search_query_id=query_id, cluster_id=cluster_id,
        observed_at=datetime(2026, 8, 17, tzinfo=timezone.utc), payload_sha256="b" * 64,
        import_batch_id=batch_id, source_artifact_id=artifact_id,
        imported_at=datetime(2026, 8, 18, tzinfo=timezone.utc), snapshot_values=_values())
    for field in ("observed_at", "imported_at"):
        invalid = {**base, field: datetime(2026, 8, 17)}
        with pytest.raises(ValueError, match="timezone-aware"):
            repo.resolve_revision(**invalid)
    for values in ({k: v for k, v in _values().items() if k != SEARCH_VISIBILITY_PAYLOAD_FIELDS[0]}, {**_values(), "extra": 1}):
        with pytest.raises(ValueError, match="fields"):
            repo.resolve_revision(**{**base, "snapshot_values": values})
    assert connection.execute("SELECT count(*) FROM search_visibility_snapshots").fetchone()[0] == 0


def test_database_unique_constraint_defends_duplicate_revision(state):
    connection, *_ = state
    first = _write(state).snapshot
    columns = [row[1] for row in connection.execute("PRAGMA table_info(search_visibility_snapshots)")]
    values = list(connection.execute("SELECT * FROM search_visibility_snapshots WHERE id=?", (first.id,)).fetchone())
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            f"INSERT INTO search_visibility_snapshots ({','.join(columns[1:])}) VALUES ({','.join('?' for _ in columns[1:])})",
            values[1:],
        )


def test_offset_datetimes_are_stored_and_found_as_utc(state):
    _, repo, product_id, query_id, cluster_id, *_ = state
    offset_time = datetime(2026, 8, 17, 6, 55, tzinfo=timezone(timedelta(hours=3)))
    written = _write(state, observed_at=offset_time)

    assert written.snapshot.observed_at == datetime(2026, 8, 17, 3, 55, tzinfo=timezone.utc)
    assert repo.find_current(product_id=product_id, search_query_id=query_id, cluster_id=cluster_id,
        observed_at=offset_time) == written.snapshot
