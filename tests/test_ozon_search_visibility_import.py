from io import BytesIO

import pytest

import backend.application.ozon_search_visibility_import as service
from backend.application.import_runtime import IMPORT_LOCK
from backend.application.ozon_products_import import import_ozon_products_xlsx
from backend.domain.search_visibility import (
    OzonSearchVisibilityImportFailure,
    SearchVisibilityConcurrentImportConflict,
    SearchVisibilityImportPersistenceError,
    SearchVisibilityNoUsableRows,
    SearchVisibilityUnsupportedUploadMediaType,
    SearchVisibilityUploadTooLarge,
)
from backend.application.ozon_search_visibility_import import (
    import_ozon_search_visibility_xlsx,
    recover_interrupted_ozon_search_visibility_imports,
)
from backend.domain.lineage import ImportStatus
from backend.persistence.connection import connect
from backend.persistence.database import initialize_database
from tests.xlsx_factory import (
    OZON_SEARCH_VISIBILITY_HEADERS,
    build_ozon_search_visibility_workbook,
)


def _row(**changes):
    row = dict(zip(OZON_SEARCH_VISIBILITY_HEADERS, (
        "1", 100000001, "Товар", "Продавец", "0,526", "Продвигается",
        "10,50 ₽", "Автостратегия", "5%", "99,1", "4,8 (1 234 шт.)",
        "1 999 ₽", "42,2", "Да", "1-2 дня", "10,0%",
    ), strict=True))
    row.update(changes)
    return row


def test_import_is_archived_and_same_payload_is_duplicate(tmp_path):
    db = tmp_path / "scoz.db"
    data = tmp_path / "data"
    initialize_database(db)
    workbook = build_ozon_search_visibility_workbook()
    first = import_ozon_search_visibility_xlsx(
        upload=BytesIO(workbook), original_name="../report.xlsx", db_path=db, data_dir=data
    )
    second = import_ozon_search_visibility_xlsx(
        upload=BytesIO(workbook), original_name="report.xlsx", db_path=db, data_dir=data
    )
    assert first.new_observations == 1
    assert second.duplicate_observations == 1
    assert first.source_artifact.original_name == "report.xlsx"
    assert (data / first.source_artifact.stored_relpath).is_file()
    with connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM search_visibility_snapshots").fetchone()[0] == 1
        assert conn.execute("SELECT is_owned FROM products").fetchone()[0] == 0


def test_visibility_only_product_does_not_enter_catalog(tmp_path):
    db = tmp_path / "scoz.db"
    initialize_database(db)
    import_ozon_search_visibility_xlsx(
        upload=BytesIO(build_ozon_search_visibility_workbook()), original_name="report.xlsx",
        db_path=db, data_dir=tmp_path / "data",
    )
    with connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM product_snapshots").fetchone()[0] == 0


def test_staging_sha_size_fsync_and_archive(monkeypatch, tmp_path):
    db, data = tmp_path / "scoz.db", tmp_path / "data"
    initialize_database(db)
    payload = build_ozon_search_visibility_workbook()
    fsynced = []
    parsed_paths = []
    real_parse = service.parse_ozon_search_visibility_xlsx
    monkeypatch.setattr(service.os, "fsync", lambda fd: fsynced.append(fd))
    monkeypatch.setattr(service, "parse_ozon_search_visibility_xlsx",
                        lambda path: (parsed_paths.append(path), real_parse(path))[1])
    result = import_ozon_search_visibility_xlsx(
        upload=BytesIO(payload), original_name="report.xlsx", db_path=db, data_dir=data,
    )
    assert fsynced and parsed_paths[0].name.startswith(".upload-")
    assert parsed_paths[0].suffix == ".part" and not parsed_paths[0].exists()
    assert result.source_artifact.byte_size == len(payload)
    assert len(result.source_artifact.content_sha256) == 64


def test_upload_boundary_and_wrong_extension_have_no_side_effects(monkeypatch, tmp_path):
    db, data = tmp_path / "scoz.db", tmp_path / "data"
    initialize_database(db)
    monkeypatch.setattr(service, "MAX_UPLOAD_BYTES", 4)
    with pytest.raises(OzonSearchVisibilityImportFailure) as exact:
        import_ozon_search_visibility_xlsx(upload=BytesIO(b"12345"), original_name="x.xlsx",
                                           db_path=db, data_dir=data)
    assert isinstance(exact.value.error, SearchVisibilityUploadTooLarge)
    with pytest.raises(OzonSearchVisibilityImportFailure) as wrong:
        import_ozon_search_visibility_xlsx(upload=BytesIO(b"1234"), original_name="x.xls",
                                           db_path=db, data_dir=data)
    assert isinstance(wrong.value.error, SearchVisibilityUnsupportedUploadMediaType)
    with connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM import_batches").fetchone()[0] == 0
    assert not list((data / "imports").glob("*"))


def test_partial_zero_usable_and_fatal_parser_do_not_mutate_domain(tmp_path):
    db, data = tmp_path / "scoz.db", tmp_path / "data"
    initialize_database(db)
    partial = build_ozon_search_visibility_workbook(rows=(_row(), _row(**{"ID товара": True})))
    result = import_ozon_search_visibility_xlsx(
        upload=BytesIO(partial), original_name="partial.xlsx", db_path=db, data_dir=data,
    )
    assert result.status is ImportStatus.PARTIAL_SUCCESS
    assert (result.rows_accepted, result.rows_skipped, result.row_errors_total) == (1, 1, 1)
    invalid = build_ozon_search_visibility_workbook(rows=(_row(**{"ID товара": True}),))
    with pytest.raises(OzonSearchVisibilityImportFailure) as no_rows:
        import_ozon_search_visibility_xlsx(upload=BytesIO(invalid), original_name="none.xlsx",
                                           db_path=db, data_dir=data)
    assert isinstance(no_rows.value.error, SearchVisibilityNoUsableRows)
    assert no_rows.value.result.status is ImportStatus.FAILED
    with pytest.raises(OzonSearchVisibilityImportFailure):
        import_ozon_search_visibility_xlsx(upload=BytesIO(b"not-xlsx"), original_name="bad.xlsx",
                                           db_path=db, data_dir=data)
    with connect(db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM search_visibility_snapshots").fetchone()[0] == 1


def test_duplicate_correction_and_independent_logical_keys(tmp_path):
    db, data = tmp_path / "scoz.db", tmp_path / "data"
    initialize_database(db)
    def load(*, row=None, query="q", cluster="c", date="17/08/2026"):
        return import_ozon_search_visibility_xlsx(
            upload=BytesIO(build_ozon_search_visibility_workbook(
                rows=(row or _row(),), query=query, cluster=cluster, date=date,
            )), original_name="x.xlsx", db_path=db, data_dir=data,
        )
    assert load().new_observations == 1
    assert load().duplicate_observations == 1
    assert load(row=_row(**{"Позиция": "2"})).corrected_revisions == 1
    assert load(query="Q").new_observations == 1
    assert load(cluster="C").new_observations == 1
    assert load(date="18/08/2026").new_observations == 1


def test_shared_cross_kind_lock_rejects_both_imports(tmp_path):
    db = tmp_path / "scoz.db"
    initialize_database(db)
    IMPORT_LOCK.acquire()
    try:
        with pytest.raises(OzonSearchVisibilityImportFailure) as failure:
            import_ozon_search_visibility_xlsx(
                upload=BytesIO(b""), original_name="x.xlsx", db_path=db, data_dir=tmp_path / "data",
            )
        assert isinstance(failure.value.error, SearchVisibilityConcurrentImportConflict)
        from backend.domain.product_snapshot import OzonProductsImportFailure, ConcurrentImportConflict
        with pytest.raises(OzonProductsImportFailure) as products:
            import_ozon_products_xlsx(
                upload=BytesIO(b""), original_name="x.xlsx", db_path=db, data_dir=tmp_path / "data",
            )
        assert isinstance(products.value.error, ConcurrentImportConflict)
    finally:
        IMPORT_LOCK.release()


def test_persistence_failure_compensates_and_removes_archive(monkeypatch, tmp_path):
    db, data = tmp_path / "scoz.db", tmp_path / "data"
    initialize_database(db)
    monkeypatch.setattr(service.SearchDimensionRepository, "resolve_cluster",
                        lambda self, name: (_ for _ in ()).throw(RuntimeError("injected")))
    with pytest.raises(OzonSearchVisibilityImportFailure) as failure:
        import_ozon_search_visibility_xlsx(
            upload=BytesIO(build_ozon_search_visibility_workbook()), original_name="x.xlsx",
            db_path=db, data_dir=data,
        )
    assert isinstance(failure.value.error, SearchVisibilityImportPersistenceError)
    assert failure.value.result.status is ImportStatus.FAILED
    assert failure.value.result.source_artifact.stored_relpath is None
    assert not list((data / "imports").glob("*.xlsx"))
    with connect(db) as conn:
        for table in ("search_queries", "clusters", "products", "search_visibility_snapshots"):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_early_persistence_failure_is_mapped_and_cleans_stage(monkeypatch, tmp_path):
    db, data = tmp_path / "scoz.db", tmp_path / "data"
    initialize_database(db)
    monkeypatch.setattr(
        service.LineageRepository, "create_import_batch",
        lambda self, **kwargs: (_ for _ in ()).throw(RuntimeError("injected")),
    )
    with pytest.raises(OzonSearchVisibilityImportFailure) as failure:
        import_ozon_search_visibility_xlsx(
            upload=BytesIO(build_ozon_search_visibility_workbook()),
            original_name="x.xlsx", db_path=db, data_dir=data,
        )
    assert isinstance(failure.value.error, SearchVisibilityImportPersistenceError)
    assert failure.value.result is None
    assert not list((data / "imports").glob("*"))
    assert IMPORT_LOCK.acquire(blocking=False)
    IMPORT_LOCK.release()


def test_recovery_is_kind_scoped_and_protects_global_archive_references(tmp_path):
    db, data = tmp_path / "scoz.db", tmp_path / "data"
    imports = data / "imports"
    imports.mkdir(parents=True)
    initialize_database(db)
    names = {
        "products": "20260817T035500000000Z-" + "a" * 64 + ".xlsx",
        "visibility": "20260817T035501000000Z-" + "b" * 64 + ".xlsx",
        "orphan": "20260817T035502000000Z-" + "c" * 64 + ".xlsx",
    }
    for name in names.values():
        (imports / name).write_bytes(b"x")
    (imports / ".upload-dead.part").write_bytes(b"x")
    (imports / "manual.xlsx").write_bytes(b"x")
    with service.transaction(db) as conn:
        lineage = service.LineageRepository(conn)
        product_batch = lineage.create_import_batch(source="ozon", import_kind="ozon_products_xlsx")
        visibility_batch = lineage.create_import_batch(
            source="ozon", import_kind="ozon_search_visibility_xlsx"
        )
        for batch, name in ((product_batch, names["products"]),
                            (visibility_batch, names["visibility"])):
            lineage.add_source_artifact(
                batch.id, artifact_kind=batch.import_kind, original_name="x.xlsx",
                content_sha256="d" * 64, byte_size=1,
                stored_relpath=f"imports/{name}",
            )
    recover_interrupted_ozon_search_visibility_imports(db_path=db, data_dir=data)
    assert (imports / names["products"]).exists()
    assert (imports / names["visibility"]).exists()
    assert (imports / "manual.xlsx").exists()
    assert not (imports / names["orphan"]).exists()
    assert not (imports / ".upload-dead.part").exists()
    with connect(db) as conn:
        statuses = dict(conn.execute("SELECT import_kind, status FROM import_batches"))
    assert statuses["ozon_products_xlsx"] == "RUNNING"
    assert statuses["ozon_search_visibility_xlsx"] == "FAILED"


def test_row_error_detail_is_capped_without_losing_total(tmp_path):
    db = tmp_path / "scoz.db"
    initialize_database(db)
    rows = (_row(),) + tuple(
        _row(**{"ID товара": True, "Название товара": f"bad-{index}"})
        for index in range(52)
    )
    result = import_ozon_search_visibility_xlsx(
        upload=BytesIO(build_ozon_search_visibility_workbook(rows=rows)),
        original_name="errors.xlsx", db_path=db, data_dir=tmp_path / "data",
    )
    assert result.status is ImportStatus.PARTIAL_SUCCESS
    assert result.row_errors_total == 52
    assert len(result.row_errors) == 50 and result.row_errors_truncated is True
    assert [error.row for error in result.row_errors] == list(range(11, 61))
