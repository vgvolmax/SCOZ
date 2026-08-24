import sqlite3
from dataclasses import fields
from datetime import datetime, timedelta, timezone

import pytest

from backend.domain.product import (
    ExternalIdentityConflict,
    Product,
    ProductExternalIdentity,
    ProductNotFound,
)
from backend.domain.lineage import datetime_from_db, datetime_to_db, utc_now
from backend.persistence.connection import connect
from backend.persistence.database import initialize_database
from backend.persistence.repositories.products import ProductRepository


@pytest.fixture
def repository(tmp_path):
    db_path = tmp_path / "scoz.db"
    initialize_database(db_path)
    connection = connect(db_path)
    try:
        yield ProductRepository(connection), connection
    finally:
        connection.close()


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


def test_visibility_only_product_stays_out_of_catalog_even_when_owned(repository):
    repo, _ = repository
    product = repo.resolve_or_create_ozon_product("12345")
    repo.set_owned(product.id, True)

    assert repo.list_ozon_products(limit=10, offset=0) == []
    assert repo.count_ozon_products() == 0
    assert repo.any_owned() is False
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
    assert repo.list_ozon_products(limit=10, offset=0) == []
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
    }

    connection.execute("BEGIN")
    repo.create_product(is_owned=False)
    assert connection.in_transaction
    connection.rollback()
