from io import BytesIO

import pytest

from backend.application.ozon_seller_queries_import import (
    import_ozon_seller_queries_xlsx, recover_interrupted_ozon_seller_queries_imports,
)
from backend.domain.lineage import ImportStatus
from backend.domain.product_query import (
    OzonSellerQueriesImportFailure, SellerQueriesUnsupportedUploadMediaType,
)
from backend.persistence.connection import connect, transaction
from backend.persistence.database import initialize_database
from backend.persistence.repositories.lineage import LineageRepository
from backend.persistence.repositories.products import ProductRepository
from tests.xlsx_factory import build_ozon_seller_queries_workbook


def test_valid_import_is_owned_and_duplicate_is_counted(tmp_path):
    db = tmp_path / "scoz.db"
    data = tmp_path / "data"
    initialize_database(db)
    payload = build_ozon_seller_queries_workbook()
    first = import_ozon_seller_queries_xlsx(
        upload=BytesIO(payload), original_name="seller.xlsx", db_path=db, data_dir=data)
    assert first.status is ImportStatus.SUCCESS
    assert (first.rows_seen, first.rows_accepted, first.new_observations) == (1, 1, 1)
    assert first.source_artifact.byte_size == len(payload)
    assert (data / first.source_artifact.stored_relpath).read_bytes() == payload
    second = import_ozon_seller_queries_xlsx(
        upload=BytesIO(payload), original_name="seller.xlsx", db_path=db, data_dir=data)
    assert (second.rows_accepted, second.duplicate_observations) == (1, 1)
    with connect(db) as conn:
        product = ProductRepository(conn).find_by_external_identity(
            source="ozon", identity_type="ozon_product_id", identity_value="100000001")
        assert product is not None and product.is_owned
        assert ProductRepository(conn).count_ozon_products() == 0
        assert conn.execute("SELECT COUNT(*) FROM product_query_snapshots").fetchone()[0] == 1


def test_unsupported_extension_has_no_durable_side_effect(tmp_path):
    db = tmp_path / "scoz.db"
    initialize_database(db)
    with pytest.raises(OzonSellerQueriesImportFailure) as caught:
        import_ozon_seller_queries_xlsx(
            upload=BytesIO(b"x"), original_name="seller.csv", db_path=db,
            data_dir=tmp_path / "data")
    assert isinstance(caught.value.error, SellerQueriesUnsupportedUploadMediaType)
    assert caught.value.result is None
    with connect(db) as conn:
        assert LineageRepository(conn).count_import_history() == 0


def test_recovery_fails_running_and_cleans_only_owned_patterns(tmp_path):
    db = tmp_path / "scoz.db"
    data = tmp_path / "data"
    imports = data / "imports"
    imports.mkdir(parents=True)
    initialize_database(db)
    with transaction(db) as conn:
        batch = LineageRepository(conn).create_import_batch(
            source="ozon", import_kind="ozon_seller_queries_xlsx")
    stale = imports / ".upload-stale.part"
    manual = imports / "manual.xlsx"
    stale.write_bytes(b"x")
    manual.write_bytes(b"x")
    recover_interrupted_ozon_seller_queries_imports(db_path=db, data_dir=data)
    assert not stale.exists() and manual.exists()
    with connect(db) as conn:
        assert LineageRepository(conn).get_import_batch(batch.id).status is ImportStatus.FAILED
