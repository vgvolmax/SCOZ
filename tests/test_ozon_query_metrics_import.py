from hashlib import sha256
from io import BytesIO

import pytest

import backend.application.ozon_query_metrics_import as query_metrics_service
from backend.application.import_runtime import IMPORT_LOCK
from backend.application.ozon_query_metrics_import import (
    import_ozon_query_metrics_xlsx, recover_interrupted_ozon_query_metrics_imports,
)
from backend.domain.lineage import ImportStatus
from backend.domain.query_metric import (
    OzonQueryMetricsImportFailure, QueryMetricsImportPersistenceError,
    QueryMetricsUnsupportedUploadMediaType,
)
from backend.persistence.connection import connect, transaction
from backend.persistence.database import initialize_database
from backend.persistence.repositories.lineage import LineageRepository
from backend.persistence.repositories.search_dimensions import SearchDimensionRepository
from tests.xlsx_factory import build_ozon_query_metrics_workbook
from tests.xlsx_factory import OZON_QUERY_METRICS_HEADERS as H


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


def test_partial_correction_and_new_period_lifecycle(tmp_path):
    db=tmp_path/'scoz.db';data=tmp_path/'data';initialize_database(db)
    good=dict(zip(H,('q',1,'-',0,1,0,1,1,1,0,0),strict=True));bad={**good,H[0]:'bad',H[1]:-1}
    partial=import_ozon_query_metrics_xlsx(upload=BytesIO(build_ozon_query_metrics_workbook(rows=(good,bad))),original_name='a.xlsx',db_path=db,data_dir=data)
    changed=import_ozon_query_metrics_xlsx(upload=BytesIO(build_ozon_query_metrics_workbook(rows=({**good,H[1]:2},))),original_name='b.xlsx',db_path=db,data_dir=data)
    period=import_ozon_query_metrics_xlsx(upload=BytesIO(build_ozon_query_metrics_workbook(rows=(good,),period='22.07.2026 - 17.08.2026')),original_name='c.xlsx',db_path=db,data_dir=data)
    assert partial.status is ImportStatus.PARTIAL_SUCCESS and (partial.rows_accepted,partial.rows_skipped)==(1,1)
    assert changed.corrected_revisions==1 and period.new_observations==1
    assert not list((data/'imports').glob('.readcopy-*'))
    with connect(db) as conn:
        assert conn.execute('SELECT COUNT(*) FROM products').fetchone()[0]==0
        assert conn.execute('SELECT COUNT(*) FROM clusters').fetchone()[0]==0


@pytest.mark.parametrize('payload', [b'bad', build_ozon_query_metrics_workbook(rows=({H[0]:'q',H[1]:-1},))])
def test_readcopy_is_cleaned_on_fatal_and_zero_usable(tmp_path,payload):
    db=tmp_path/'scoz.db';data=tmp_path/'data';initialize_database(db)
    with pytest.raises(OzonQueryMetricsImportFailure):
        import_ozon_query_metrics_xlsx(upload=BytesIO(payload),original_name='x.xlsx',db_path=db,data_dir=data)
    assert not list((data/'imports').glob('.readcopy-*'))


def test_recovery_preserves_referenced_archive_and_manual_file(tmp_path):
    db=tmp_path/'scoz.db';data=tmp_path/'data';initialize_database(db)
    result=import_ozon_query_metrics_xlsx(upload=BytesIO(build_ozon_query_metrics_workbook()),original_name='x.xlsx',db_path=db,data_dir=data)
    manual=data/'imports'/'manual.xlsx';manual.write_bytes(b'manual')
    recover_interrupted_ozon_query_metrics_imports(db_path=db,data_dir=data)
    assert manual.exists() and (data/result.source_artifact.stored_relpath).exists()


def test_unexpected_programming_error_is_compensated_and_preserved(monkeypatch, tmp_path):
    db = tmp_path / "scoz.db"
    data = tmp_path / "data"
    initialize_database(db)

    def raise_programming_error(*args, **kwargs):
        raise RuntimeError("programming-test-sentinel")

    monkeypatch.setattr(
        SearchDimensionRepository, "resolve_search_query", raise_programming_error
    )
    with pytest.raises(RuntimeError, match="programming-test-sentinel"):
        import_ozon_query_metrics_xlsx(
            upload=BytesIO(build_ozon_query_metrics_workbook()),
            original_name="metrics.xlsx",
            db_path=db,
            data_dir=data,
        )

    assert not IMPORT_LOCK.locked()
    with connect(db) as conn:
        assert conn.execute(
            "SELECT status FROM import_batches "
            "WHERE import_kind='ozon_query_metrics_xlsx' ORDER BY id DESC LIMIT 1"
        ).fetchone()["status"] == "FAILED"
        for table in ("search_queries", "query_metric_snapshots"):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    imports = data / "imports"
    assert not list(imports.glob(".upload-*"))
    assert not list(imports.glob(".readcopy-*"))
    assert not list(imports.glob("*.xlsx"))


def test_archive_failure_cleans_all_helper_owned_files(monkeypatch, tmp_path):
    db = tmp_path / "scoz.db"
    data = tmp_path / "data"
    initialize_database(db)

    def fail_publish(*args, **kwargs):
        raise OSError("archive-test-sentinel")

    monkeypatch.setattr(query_metrics_service, "publish_staged_archive", fail_publish)
    with pytest.raises(OzonQueryMetricsImportFailure) as caught:
        import_ozon_query_metrics_xlsx(
            upload=BytesIO(build_ozon_query_metrics_workbook()),
            original_name="metrics.xlsx",
            db_path=db,
            data_dir=data,
        )

    assert isinstance(caught.value.error, QueryMetricsImportPersistenceError)
    assert caught.value.result.status is ImportStatus.FAILED
    imports = data / "imports"
    assert not list(imports.glob(".readcopy-*"))
    assert not list(imports.glob(".upload-*"))
    assert not list(imports.glob("*.xlsx"))
    assert not IMPORT_LOCK.locked()
