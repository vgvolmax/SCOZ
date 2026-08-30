import sqlite3
from dataclasses import fields
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.domain.product import (
    ExternalIdentityConflict,
    Product,
    ProductExternalIdentity,
    ProductNotFound,
)
from backend.domain.lineage import datetime_from_db, datetime_to_db, utc_now
from backend.domain.product_workspace import ProductDataStatus
from backend.domain.product_snapshot import PAYLOAD_FIELDS
from backend.persistence.connection import connect
from backend.persistence.database import initialize_database
from backend.persistence.repositories.products import ProductRepository
from backend.persistence.repositories.lineage import LineageRepository
from backend.persistence.repositories.product_snapshots import ProductSnapshotRepository


@pytest.fixture
def repository(tmp_path):
    db_path = tmp_path / "scoz.db"
    initialize_database(db_path)
    connection = connect(db_path)
    try:
        yield ProductRepository(connection), connection
    finally:
        connection.close()


def _snapshot(repo, connection, ozon_id, title, *, seller="Seller", brand="Brand"):
    product = repo.resolve_or_create_ozon_product(ozon_id)
    lineage = LineageRepository(connection)
    batch = lineage.create_import_batch(source="ozon", import_kind="test")
    artifact = lineage.add_source_artifact(batch.id, artifact_kind="test", original_name="test.xlsx",
        content_sha256=f"{product.id:064x}", byte_size=1)
    values = {name: 0 for name in PAYLOAD_FIELDS}
    values.update(product_url=f"https://www.ozon.ru/product/{ozon_id}", title=title,
        seller_name=seller, brand=brand, category_level_1="L1", category_level_3="L3",
        product_badges=None, ordered_amount_rub=Decimal("1"), turnover_change_pct=Decimal("0"),
        average_price_rub=Decimal("1"), minimum_price_rub=Decimal("1"), buyout_share_pct=None,
        missed_sales_source_value=Decimal("0"), out_of_stock_days=None, out_of_stock_window_days=None,
        avg_daily_sales_rub=Decimal("0"), fulfillment_scheme="FBO", volume_l=Decimal("1"),
        impression_to_order_pct=Decimal("0"), search_catalog_to_cart_pct=Decimal("0"),
        card_to_cart_pct=Decimal("0"), promotion_discount_source_value=Decimal("0"),
        promotion_order_amount_share_pct=Decimal("0"), total_drr_pct=Decimal("0"),
        promotion_window_days=7, advertising_window_days=7, card_created_on=date(2026, 1, 1))
    ProductSnapshotRepository(connection).resolve_revision(product_id=product.id,
        report_generated_on=date(2026, 8, 30), report_window_days=7,
        payload_sha256=f"{product.id + 1000:064x}", import_batch_id=batch.id,
        source_artifact_id=artifact.id, imported_at=datetime(2026, 8, 30, tzinfo=timezone.utc),
        snapshot_values=values)
    return product


def test_create_and_get_owned_and_non_owned_products(repository):
    repo, _ = repository

    owned = repo.create_product(is_owned=True)
    competitor = repo.create_product(is_owned=False)

    assert isinstance(owned, Product)
    assert owned.is_owned is True
    assert competitor.is_owned is False
    assert owned.created_at.tzinfo == timezone.utc
    assert owned.updated_at.tzinfo == timezone.utc
    assert repo.get_product(owned.id) == owned
    assert repo.get_product(999_999) is None


def test_shared_datetime_helpers_normalize_and_round_trip_aware_utc():
    offset = timezone(timedelta(hours=3))
    source = datetime(2026, 8, 16, 12, 30, tzinfo=offset)

    stored = datetime_to_db(source)
    restored = datetime_from_db(stored)

    assert restored == datetime(2026, 8, 16, 9, 30, tzinfo=timezone.utc)
    assert restored.tzinfo == timezone.utc
    assert utc_now().tzinfo == timezone.utc
    with pytest.raises(ValueError, match="timezone-aware"):
        datetime_to_db(datetime(2026, 8, 16))


def test_set_owned_updates_timestamp_and_missing_product_raises(repository):
    repo, _ = repository
    product = repo.create_product(is_owned=False)

    updated = repo.set_owned(product.id, True)

    assert updated.is_owned is True
    assert updated.updated_at > product.updated_at
    assert updated.created_at == product.created_at
    with pytest.raises(ProductNotFound):
        repo.set_owned(999_999, True)


def test_identity_only_owned_product_is_my_product_but_not_full_catalog(repository):
    repo, _ = repository
    product = repo.resolve_or_create_ozon_product("12345")
    repo.set_owned(product.id, True)

    assert repo.list_ozon_products(limit=10, offset=0) == ()
    assert repo.count_ozon_products() == 0
    assert repo.any_owned() is False
    owned = repo.list_owned_ozon_products()
    assert len(owned) == 1
    assert owned[0].product_id == product.id
    assert owned[0].ozon_product_id == "12345"
    assert owned[0].product_data_status is ProductDataStatus.MISSING
    assert owned[0].title is owned[0].seller_name is owned[0].brand is None
    assert owned[0].report_generated_on is owned[0].report_window_days is owned[0].imported_at is None
    assert repo.get_ozon_product_entry(product.id) == owned[0]
    assert repo.find_by_external_identity(
        source="ozon", identity_type="ozon_product_id", identity_value="12345"
    ).is_owned is True


@pytest.mark.parametrize("value", ["0", "00", "01", "-1", "+1", " 1", "1 ", "abc", "١", "１"])
def test_resolver_rejects_zero_leading_zero_and_nondigit_ozon_ids(repository, value):
    repo, connection = repository
    with pytest.raises(ValueError, match="invalid Ozon product ID"):
        repo.resolve_or_create_ozon_product(value)
    assert connection.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0


def test_resolver_reuses_existing_canonical_identity(repository):
    repo, _ = repository
    first = repo.resolve_or_create_ozon_product("123")
    assert repo.resolve_or_create_ozon_product("123") == first


def test_identity_only_product_is_not_in_catalog_projection(repository):
    repo, _ = repository
    repo.resolve_or_create_ozon_product("456")
    assert repo.list_ozon_products(limit=10, offset=0) == ()
    assert repo.count_ozon_products() == 0


def test_external_identity_insert_and_lookup(repository):
    repo, _ = repository
    product = repo.create_product(is_owned=True)

    identity = repo.add_external_identity(
        product.id,
        source="ozon",
        identity_type="sku",
        identity_value="12345",
    )

    assert isinstance(identity, ProductExternalIdentity)
    assert identity.product_id == product.id
    assert identity.source_account_scope == ""
    assert identity.created_at.tzinfo == timezone.utc
    assert (
        repo.find_by_external_identity(
            source="ozon", identity_type="sku", identity_value="12345"
        )
        == product
    )


def test_missing_parent_is_product_error_and_creates_no_identity(repository):
    repo, connection = repository

    with pytest.raises(ProductNotFound):
        repo.add_external_identity(
            999_999, source="ozon", identity_type="sku", identity_value="missing"
        )

    assert connection.execute(
        "SELECT COUNT(*) FROM product_external_identities"
    ).fetchone()[0] == 0


def test_scoped_identity_conflict_and_distinct_scopes(repository):
    repo, _ = repository
    first = repo.create_product(is_owned=True)
    second = repo.create_product(is_owned=False)
    repo.add_external_identity(
        first.id,
        source="ozon",
        identity_type="sku",
        identity_value="same",
        source_account_scope="account-a",
    )

    with pytest.raises(ExternalIdentityConflict):
        repo.add_external_identity(
            second.id,
            source="ozon",
            identity_type="sku",
            identity_value="same",
            source_account_scope="account-a",
        )

    other_scope = repo.add_external_identity(
        second.id,
        source="ozon",
        identity_type="sku",
        identity_value="same",
        source_account_scope="account-b",
    )
    assert other_scope.product_id == second.id


def test_unrelated_integrity_errors_propagate(repository):
    repo, connection = repository
    product = repo.create_product(is_owned=True)
    connection.execute(
        """CREATE TRIGGER reject_identity BEFORE INSERT ON product_external_identities
           BEGIN SELECT RAISE(ABORT, 'unrelated'); END"""
    )

    with pytest.raises(sqlite3.IntegrityError, match="unrelated"):
        repo.add_external_identity(
            product.id, source="ozon", identity_type="sku", identity_value="1"
        )


def test_unrelated_trigger_error_is_not_mapped_when_identity_already_exists(repository):
    repo, connection = repository
    first = repo.create_product(is_owned=True)
    second = repo.create_product(is_owned=False)
    repo.add_external_identity(
        first.id, source="ozon", identity_type="sku", identity_value="duplicate"
    )
    connection.execute(
        """CREATE TRIGGER reject_duplicate BEFORE INSERT ON product_external_identities
           BEGIN SELECT RAISE(ABORT, 'unrelated trigger'); END"""
    )

    with pytest.raises(sqlite3.IntegrityError, match="unrelated trigger") as raised:
        repo.add_external_identity(
            second.id,
            source="ozon",
            identity_type="sku",
            identity_value="duplicate",
        )

    assert raised.value.sqlite_errorname == "SQLITE_CONSTRAINT_TRIGGER"


def test_domain_and_repository_boundary_is_narrow(repository):
    repo, connection = repository
    assert [field.name for field in fields(Product)] == [
        "id", "is_owned", "created_at", "updated_at"
    ]
    assert [field.name for field in fields(ProductExternalIdentity)] == [
        "id", "product_id", "source", "identity_type", "identity_value",
        "source_account_scope", "created_at",
    ]
    assert set(name for name in vars(ProductRepository) if not name.startswith("_")) == {
        "create_product", "get_product", "set_owned", "add_external_identity",
        "find_by_external_identity", "resolve_or_create_ozon_product",
        "count_ozon_products", "any_owned", "list_ozon_products",
        "list_owned_ozon_products", "get_ozon_product_entry",
    }

    connection.execute("BEGIN")
    repo.create_product(is_owned=False)
    assert connection.in_transaction
    connection.rollback()


@pytest.mark.parametrize("query", ["", "   ", " x", "x ", "x" * 201])
def test_catalog_query_requires_normalized_nonempty_text(repository, query):
    repo, _ = repository
    with pytest.raises(ValueError, match="invalid product query"):
        repo.count_ozon_products(query=query)
    with pytest.raises(ValueError, match="invalid product query"):
        repo.list_ozon_products(limit=50, offset=0, query=query)


@pytest.mark.parametrize("limit,offset", [(0, 0), (101, 0), (50, -1)])
def test_catalog_list_rejects_invalid_pagination(repository, limit, offset):
    repo, _ = repository
    with pytest.raises(ValueError, match="invalid pagination"):
        repo.list_ozon_products(limit=limit, offset=offset)


def test_catalog_search_has_frozen_title_and_id_semantics(repository):
    repo, connection = repository
    _snapshot(repo, connection, "100000001", "Альфа: Смеситель кухонный 1000")
    _snapshot(repo, connection, "100000002", "Бета модель", seller="Смеситель продавец")
    _snapshot(repo, connection, "200000001", "Процент % и знак _", brand="Смеситель бренд")

    def ids(query):
        return [item.ozon_product_id for item in repo.list_ozon_products(limit=50, offset=0, query=query)]

    assert ids("смЕСИТЕЛЬ") == ["100000001"]
    assert ids("кухон") == ["100000001"]
    assert ids("продавец") == []
    assert ids("бренд") == []
    assert ids("1000") == ["100000001", "100000002"]
    assert ids("١٠٠٠") == []
    assert ids("%") == ["200000001"]
    assert ids("_") == ["200000001"]
    for query in ("смЕСИТЕЛЬ", "1000", "%", "_"):
        assert repo.count_ozon_products(query=query) == len(ids(query))


def test_catalog_order_is_casefold_then_id_length_text_then_product_id(repository):
    repo, connection = repository
    products = [_snapshot(repo, connection, ozon_id, title)
        for ozon_id, title in (("20", "Бета"), ("3", "бета"), ("10", "БЕТА"))]
    ordered = repo.list_ozon_products(limit=50, offset=0)
    assert [item.ozon_product_id for item in ordered] == ["3", "10", "20"]
    assert {item.product_id for item in ordered} == {product.id for product in products}


def test_ambiguous_or_missing_canonical_identity_is_not_projected(repository):
    repo, _ = repository
    missing = repo.create_product(is_owned=True)
    ambiguous = repo.resolve_or_create_ozon_product("123")
    repo.set_owned(ambiguous.id, True)
    repo.add_external_identity(ambiguous.id, source="ozon", identity_type="ozon_product_id",
        identity_value="456")

    assert repo.get_ozon_product_entry(missing.id) is None
    assert repo.get_ozon_product_entry(ambiguous.id) is None
    assert repo.list_owned_ozon_products() == ()
