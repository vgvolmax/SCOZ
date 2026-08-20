from hashlib import sha256
from io import BytesIO

import pytest

from backend.application.ozon_query_metrics_import import (
    import_ozon_query_metrics_xlsx, recover_interrupted_ozon_query_metrics_imports,
)
from backend.domain.lineage import ImportStatus
from backend.domain.query_metric import (
    OzonQueryMetricsImportFailure, QueryMetricsUnsupportedUploadMediaType,
)
from backend.persistence.connection import connect, transaction
from backend.persistence.database import initialize_database
from backend.persistence.repositories.lineage import LineageRepository
from tests.xlsx_factory import build_ozon_query_metrics_workbook


def test_original_is_provenance_and_read_copy_is_transient(tmp_path):
    db = tmp_path / "scoz.db"
    data = tmp_path / "data"
    initialize_database(db)
    payload = build_ozon_query_metrics_workbook(horizontal_capitalized=True)
    result = import_ozon_query_metrics_xlsx(
        upload=BytesIO(payload), original_name="metrics.xlsx", db_path=db, data_dir=data)
    assert result.status is ImportStatus.SUCCESS
    assert result.source_artifact.content_sha256 == sha256(payload).hexdigest()
    assert (data / result.source_artifact.stored_relpath).read_bytes() == payload
    assert not list((data / "imports").glob(".readcopy-*.xlsx"))
    with connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM query_metric_snapshots").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM clusters").fetchone()[0] == 0


def test_database_duplicate_is_counted_without_new_snapshot(tmp_path):
    db = tmp_path / "scoz.db"
    data = tmp_path / "data"
    initialize_database(db)
    payload = build_ozon_query_metrics_workbook()
    first = import_ozon_query_metrics_xlsx(
        upload=BytesIO(payload), original_name="metrics.xlsx", db_path=db, data_dir=data)
    second = import_ozon_query_metrics_xlsx(
        upload=BytesIO(payload), original_name="metrics.xlsx", db_path=db, data_dir=data)
    assert (first.new_observations, second.duplicate_observations) == (1, 1)
    assert second.rows_accepted == 1


def test_transport_rejection_precedes_durable_batch(tmp_path):
    db = tmp_path / "scoz.db"
    initialize_database(db)
    with pytest.raises(OzonQueryMetricsImportFailure) as caught:
        import_ozon_query_metrics_xlsx(
            upload=BytesIO(b"x"), original_name="metrics.csv", db_path=db,
            data_dir=tmp_path / "data")
    assert isinstance(caught.value.error, QueryMetricsUnsupportedUploadMediaType)
    assert caught.value.result is None
    with connect(db) as conn:
        assert LineageRepository(conn).count_import_history() == 0


def test_recovery_cleans_readcopies_and_is_idempotent(tmp_path):
    db = tmp_path / "scoz.db"
    data = tmp_path / "data"
    imports = data / "imports"
    imports.mkdir(parents=True)
    initialize_database(db)
    with transaction(db) as conn:
        batch = LineageRepository(conn).create_import_batch(
            source="ozon", import_kind="ozon_query_metrics_xlsx")
    readcopy = imports / ".readcopy-stale.xlsx"
    manual = imports / "manual.xlsx"
    readcopy.write_bytes(b"x")
    manual.write_bytes(b"x")
    recover_interrupted_ozon_query_metrics_imports(db_path=db, data_dir=data)
    recover_interrupted_ozon_query_metrics_imports(db_path=db, data_dir=data)
    assert not readcopy.exists() and manual.exists()
    with connect(db) as conn:
        assert LineageRepository(conn).get_import_batch(batch.id).status is ImportStatus.FAILED


def test_service_source_has_no_product_repository_dependency():
    from backend.application import ozon_query_metrics_import as service
    assert "ProductRepository" not in open(service.__file__, encoding="utf-8").read()
