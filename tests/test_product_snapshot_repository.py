import sqlite3
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from backend.domain.product_snapshot import PAYLOAD_FIELDS, SnapshotWriteKind
from backend.persistence.connection import connect
from backend.persistence.database import initialize_database
from backend.persistence.repositories.lineage import LineageRepository
from backend.persistence.repositories.product_snapshots import ProductSnapshotRepository
from backend.persistence.repositories.products import ProductRepository


def _values(title="First"):
    values = {name: 0 for name in PAYLOAD_FIELDS}
    values.update(
        product_url="https://www.ozon.ru/product/1", title=title, seller_name="Seller",
        brand="Brand", category_level_1="L1", category_level_3="L3",
        product_badges=None, ordered_amount_rub=Decimal("1.2300"),
        turnover_change_pct=Decimal("1.31"), average_price_rub=Decimal("1"),
        minimum_price_rub=Decimal("1"), buyout_share_pct=None,
        missed_sales_source_value=Decimal("0"), out_of_stock_days=None,
        out_of_stock_window_days=None, avg_daily_sales_rub=Decimal("0"),
        fulfillment_scheme="FBO", volume_l=Decimal("1.5"),
        impression_to_order_pct=Decimal("0"), search_catalog_to_cart_pct=Decimal("0"),
        card_to_cart_pct=Decimal("0"), promotion_discount_source_value=Decimal("0"),
        promotion_order_amount_share_pct=Decimal("0"), total_drr_pct=Decimal("0"),
        promotion_window_days=7, advertising_window_days=7,
        card_created_on=date(2026, 1, 1),
    )
    return values


@pytest.fixture
def state(tmp_path):
    path = tmp_path / "scoz.db"; initialize_database(path); connection = connect(path)
    lineage = LineageRepository(connection)
    batch = lineage.create_import_batch(source="ozon", import_kind="ozon_products_xlsx")
    artifact = lineage.add_source_artifact(batch.id, artifact_kind="ozon_products_xlsx", original_name="x.xlsx", content_sha256="a" * 64, byte_size=1)
    product = ProductRepository(connection).resolve_or_create_ozon_product("1")
    try: yield connection, ProductSnapshotRepository(connection), product.id, batch.id, artifact.id
    finally: connection.close()


def _write(repo, product_id, batch_id, artifact_id, *, generated=date(2026, 8, 16), window=7, digest="b" * 64, title="First"):
    return repo.resolve_revision(product_id=product_id, report_generated_on=generated,
        report_window_days=window, payload_sha256=digest, import_batch_id=batch_id,
        source_artifact_id=artifact_id, imported_at=datetime(2026, 8, 16, tzinfo=timezone.utc),
        snapshot_values=_values(title))


def test_revision_duplicate_correction_and_latest_ordering(state):
    connection, repo, product_id, batch_id, artifact_id = state
    first = _write(repo, product_id, batch_id, artifact_id)
    duplicate = _write(repo, product_id, batch_id, artifact_id)
    corrected = _write(repo, product_id, batch_id, artifact_id, digest="c" * 64, title="Corrected")
    assert first.kind is SnapshotWriteKind.NEW and first.snapshot.revision == 1
    assert duplicate.kind is SnapshotWriteKind.DUPLICATE and duplicate.snapshot.id == first.snapshot.id
    assert corrected.kind is SnapshotWriteKind.CORRECTED and corrected.snapshot.revision == 2
    assert corrected.snapshot.supersedes_snapshot_id == first.snapshot.id
    assert repo._get(first.snapshot.id).title == "First"
    window_28 = _write(repo, product_id, batch_id, artifact_id, window=28, digest="d" * 64)
    assert window_28.snapshot.revision == 1 and repo.list_latest_current_for_products(limit=100, offset=0)[0].id == window_28.snapshot.id
    later = _write(repo, product_id, batch_id, artifact_id, generated=date(2026, 8, 17), digest="e" * 64)
    assert repo.list_latest_current_for_products(limit=100, offset=0)[0].id == later.snapshot.id
    raw = connection.execute("SELECT ordered_amount_rub FROM product_snapshots WHERE id=?", (first.snapshot.id,)).fetchone()[0]
    assert raw == "1.23" and isinstance(repo._get(first.snapshot.id).ordered_amount_rub, Decimal)


def test_frozen_current_list_count_and_pagination_interface(state):
    connection, repo, product_id, batch_id, artifact_id = state
    first = _write(repo, product_id, batch_id, artifact_id)
    corrected = _write(repo, product_id, batch_id, artifact_id, digest="c" * 64)
    other = ProductRepository(connection).resolve_or_create_ozon_product("2")
    other_latest = _write(repo, other.id, batch_id, artifact_id, generated=date(2026, 8, 18), digest="d" * 64)

    current = repo.find_current(product_id=product_id, report_generated_on=date(2026, 8, 16), report_window_days=7)
    assert current is not None and current.id == corrected.snapshot.id and current.id != first.snapshot.id
    assert repo.count_products_with_snapshots() == 2
    page = repo.list_latest_current_for_products(limit=1, offset=1)
    assert page == [other_latest.snapshot]
    with pytest.raises(ValueError): repo.list_latest_current_for_products(limit=0, offset=0)
    with pytest.raises(ValueError): repo.list_latest_current_for_products(limit=1, offset=-1)


def test_find_latest_current_prefers_newest_generated_date(state):
    _, repo, product_id, batch_id, artifact_id = state
    _write(repo, product_id, batch_id, artifact_id, generated=date(2026, 8, 20), window=28, digest="c" * 64)
    newest = _write(repo, product_id, batch_id, artifact_id, generated=date(2026, 8, 21), window=7, digest="d" * 64)
    assert repo.find_latest_current_for_product(product_id).id == newest.snapshot.id


def test_find_latest_current_prefers_longest_window_on_same_date(state):
    _, repo, product_id, batch_id, artifact_id = state
    _write(repo, product_id, batch_id, artifact_id, window=7)
    longest = _write(repo, product_id, batch_id, artifact_id, window=28, digest="c" * 64)
    assert repo.find_latest_current_for_product(product_id).id == longest.snapshot.id


def test_find_latest_current_returns_highest_revision_inside_selected_context(state):
    _, repo, product_id, batch_id, artifact_id = state
    _write(repo, product_id, batch_id, artifact_id)
    correction = _write(repo, product_id, batch_id, artifact_id, digest="c" * 64)
    assert repo.find_latest_current_for_product(product_id).id == correction.snapshot.id


def test_anchor_is_independent_of_imported_at_id_and_insert_order(state):
    _, repo, product_id, batch_id, artifact_id = state
    newest = _write(repo, product_id, batch_id, artifact_id, generated=date(2026, 8, 20), digest="c" * 64)
    _write(repo, product_id, batch_id, artifact_id, generated=date(2026, 8, 19), window=28, digest="d" * 64)
    assert repo.find_latest_current_for_product(product_id).id == newest.snapshot.id


def test_list_context_returns_current_exact_compatible_snapshots_only(state):
    connection, repo, product_id, batch_id, artifact_id = state
    first = _write(repo, product_id, batch_id, artifact_id)
    current = _write(repo, product_id, batch_id, artifact_id, digest="c" * 64)
    other = ProductRepository(connection).resolve_or_create_ozon_product("2")
    other_current = _write(repo, other.id, batch_id, artifact_id, digest="d" * 64)
    result = repo.list_current_for_products_at_context([product_id, other.id], date(2026, 8, 16), 7)
    assert result == {product_id: current.snapshot, other.id: other_current.snapshot}
    assert first.snapshot not in result.values()


def test_context_read_uses_older_exact_match_instead_of_newer_incompatible_snapshot(state):
    _, repo, product_id, batch_id, artifact_id = state
    exact = _write(repo, product_id, batch_id, artifact_id)
    _write(repo, product_id, batch_id, artifact_id, generated=date(2026, 8, 17), digest="c" * 64)
    assert repo.list_current_for_products_at_context([product_id], date(2026, 8, 16), 7)[product_id] == exact.snapshot


def test_context_read_deduplicates_requested_ids_and_excludes_unrequested_products(state):
    connection, repo, product_id, batch_id, artifact_id = state
    expected = _write(repo, product_id, batch_id, artifact_id)
    other = ProductRepository(connection).resolve_or_create_ozon_product("2")
    _write(repo, other.id, batch_id, artifact_id, digest="c" * 64)
    assert repo.list_current_for_products_at_context([product_id, product_id], date(2026, 8, 16), 7) == {product_id: expected.snapshot}


def test_context_read_handles_empty_product_ids(state):
    _, repo, _, _, _ = state
    assert repo.list_current_for_products_at_context([], date(2026, 8, 16), 7) == {}


@pytest.mark.parametrize("digest", ["A" * 64, "a" * 63, "g" * 64])
def test_invalid_hash_rejected(state, digest):
    _, repo, product_id, batch_id, artifact_id = state
    with pytest.raises(ValueError): _write(repo, product_id, batch_id, artifact_id, digest=digest)


def test_aware_import_time_required_and_unique_constraint(state):
    connection, repo, product_id, batch_id, artifact_id = state
    with pytest.raises(ValueError):
        repo.resolve_revision(product_id=product_id, report_generated_on=date(2026, 8, 16),
            report_window_days=7, payload_sha256="b" * 64, import_batch_id=batch_id,
            source_artifact_id=artifact_id, imported_at=datetime(2026, 8, 16), snapshot_values=_values())
    first = _write(repo, product_id, batch_id, artifact_id)
    columns = [row[1] for row in connection.execute("PRAGMA table_info(product_snapshots)")]
    values = list(connection.execute("SELECT * FROM product_snapshots WHERE id=?", (first.snapshot.id,)).fetchone())
    values[0] = None
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(f"INSERT INTO product_snapshots ({','.join(columns[1:])}) VALUES ({','.join('?' for _ in columns[1:])})", values[1:])
