from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO

import pytest

import backend.application.ozon_products_import as products_service
import backend.application.ozon_search_visibility_import as service
from backend.application.import_runtime import IMPORT_LOCK, MAX_UPLOAD_BYTES
from backend.domain.lineage import ImportStatus
from backend.domain.search_visibility import (
    OzonSearchVisibilityImportFailure,
    SearchVisibilityConcurrentImportConflict,
    SearchVisibilityImportPersistenceError,
    SearchVisibilityNoUsableRows,
    SearchVisibilityUnsupportedUploadMediaType,
    SearchVisibilityUnsupportedWorkbook,
    SearchVisibilityUploadTooLarge,
)
from backend.persistence.connection import transaction
from backend.persistence.database import initialize_database
from backend.persistence.repositories.lineage import LineageRepository
from backend.persistence.repositories.products import ProductRepository
from backend.persistence.repositories.search_visibility_snapshots import SearchVisibilitySnapshotRepository
from tests.xlsx_factory import (
    OZON_SEARCH_VISIBILITY_HEADERS,
    _default_search_visibility_row,
    build_ozon_search_visibility_workbook,
)


def _setup(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "scoz.db"; initialize_database(db_path)
    return db_path, tmp_path


def _import(payload, db_path, data_dir, name="search.xlsx"):
    return service.import_ozon_search_visibility_xlsx(
        upload=BytesIO(payload), original_name=name, db_path=db_path, data_dir=data_dir,
    )


def _summaries(db_path):
    with transaction(db_path) as conn:
        return LineageRepository(conn).list_ozon_search_visibility_imports(limit=100, offset=0)


def test_extension_lock_and_exact_upload_limit(monkeypatch, tmp_path):
    db_path, data_dir = _setup(tmp_path)
    with pytest.raises(OzonSearchVisibilityImportFailure) as wrong:
        _import(b"x", db_path, data_dir, "search.csv")
    assert isinstance(wrong.value.error, SearchVisibilityUnsupportedUploadMediaType)
    with pytest.raises(OzonSearchVisibilityImportFailure) as large:
        _import(b"x" * (MAX_UPLOAD_BYTES + 1), db_path, data_dir)
    assert isinstance(large.value.error, SearchVisibilityUploadTooLarge)
    assert not _summaries(db_path)
    IMPORT_LOCK.acquire()
    try:
        with pytest.raises(OzonSearchVisibilityImportFailure) as locked:
            _import(build_ozon_search_visibility_workbook(), db_path, data_dir)
        assert isinstance(locked.value.error, SearchVisibilityConcurrentImportConflict)
    finally:
        IMPORT_LOCK.release()


def test_hash_size_fsync_staging_and_parser_fatal_durable_failure(monkeypatch, tmp_path):
    db_path, data_dir = _setup(tmp_path); calls = []
    monkeypatch.setattr(service.os, "fsync", lambda fd: calls.append(fd))
    with pytest.raises(OzonSearchVisibilityImportFailure) as caught:
        _import(b"x" * MAX_UPLOAD_BYTES, db_path, data_dir, r"C:\fake\bad.xlsx")
    assert isinstance(caught.value.error, SearchVisibilityUnsupportedWorkbook)
    assert caught.value.result.status is ImportStatus.FAILED
    artifact = caught.value.result.source_artifact
    assert artifact.original_name == "bad.xlsx"
    assert artifact.byte_size == MAX_UPLOAD_BYTES
    assert artifact.content_sha256 == sha256(b"x" * MAX_UPLOAD_BYTES).hexdigest()
    assert artifact.stored_relpath is None and calls
    assert not list((data_dir / "imports").glob(".upload-*.part"))


def test_success_unknown_nonowned_archive_and_existing_owned_preserved(tmp_path):
    db_path, data_dir = _setup(tmp_path)
    with transaction(db_path) as conn:
        existing = ProductRepository(conn).resolve_or_create_ozon_product("100000001")
        ProductRepository(conn).set_owned(existing.id, True)
    result = _import(build_ozon_search_visibility_workbook(), db_path, data_dir)
    assert result.status is ImportStatus.SUCCESS and result.new_observations == 1
    assert result.report_type == "OZON_SEARCH_VISIBILITY"
    assert (data_dir / result.source_artifact.stored_relpath).is_file()
    with transaction(db_path) as conn:
        product = ProductRepository(conn).find_by_external_identity(
            source="ozon", identity_type="ozon_product_id", identity_value="100000001")
        assert product.is_owned is True
        assert conn.execute("SELECT count(*) FROM search_visibility_snapshots").fetchone()[0] == 1


def test_partial_zero_usable_duplicate_and_correction(tmp_path):
    db_path, data_dir = _setup(tmp_path)
    valid = _default_search_visibility_row()
    invalid = dict(valid); invalid[OZON_SEARCH_VISIBILITY_HEADERS[0]] = "0"
    partial = _import(build_ozon_search_visibility_workbook(rows=(valid, invalid)), db_path, data_dir)
    assert partial.status is ImportStatus.PARTIAL_SUCCESS
    assert (partial.rows_seen, partial.rows_accepted, partial.rows_skipped) == (2, 1, 1)
    with transaction(db_path) as conn:
        discovered = ProductRepository(conn).find_by_external_identity(
            source="ozon", identity_type="ozon_product_id", identity_value="100000001")
        assert discovered is not None and discovered.is_owned is False
    duplicate = _import(build_ozon_search_visibility_workbook(rows=(valid, valid)), db_path, data_dir)
    assert duplicate.status is ImportStatus.SUCCESS and duplicate.duplicate_observations >= 1
    changed = dict(valid); changed[OZON_SEARCH_VISIBILITY_HEADERS[0]] = "2"
    corrected = _import(build_ozon_search_visibility_workbook(rows=(changed,)), db_path, data_dir)
    assert corrected.corrected_revisions == 1

    empty_db, empty_dir = _setup(tmp_path / "empty")
    with pytest.raises(OzonSearchVisibilityImportFailure) as empty:
        _import(build_ozon_search_visibility_workbook(rows=(invalid,)), empty_db, empty_dir)
    assert isinstance(empty.value.error, SearchVisibilityNoUsableRows)
    assert empty.value.result.status is ImportStatus.FAILED
    assert empty.value.result.query_text == "тестовый запрос"
    with transaction(empty_db) as conn:
        assert conn.execute("SELECT count(*) FROM products").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM search_queries").fetchone()[0] == 0


def test_conflicting_rows_are_durable_fatal_and_row_details_cap_at_50(tmp_path):
    db_path, data_dir = _setup(tmp_path)
    row = _default_search_visibility_row()
    conflict = dict(row); conflict[OZON_SEARCH_VISIBILITY_HEADERS[0]] = "2"
    with pytest.raises(OzonSearchVisibilityImportFailure) as caught:
        _import(build_ozon_search_visibility_workbook(rows=(row, conflict)), db_path, data_dir)
    assert caught.value.result.status is ImportStatus.FAILED
    assert caught.value.result.source_artifact.stored_relpath is None
    with transaction(db_path) as conn:
        assert conn.execute("SELECT count(*) FROM products").fetchone()[0] == 0

    cap_db, cap_dir = _setup(tmp_path / "cap")
    rows = [row]
    for index in range(51):
        invalid = dict(row)
        invalid[OZON_SEARCH_VISIBILITY_HEADERS[0]] = "0"
        invalid[OZON_SEARCH_VISIBILITY_HEADERS[1]] = 200000000 + index
        rows.append(invalid)
    result = _import(build_ozon_search_visibility_workbook(rows=rows), cap_db, cap_dir)
    assert result.status is ImportStatus.PARTIAL_SUCCESS
    assert result.row_errors_total == 51 and len(result.row_errors) == 50
    assert result.row_errors_truncated is True
    assert [error.row for error in result.row_errors] == list(range(11, 61))


def test_changed_context_creates_independent_revision_one(tmp_path):
    db_path, data_dir = _setup(tmp_path)
    payload = build_ozon_search_visibility_workbook()
    _import(payload, db_path, data_dir)
    _import(build_ozon_search_visibility_workbook(query="other"), db_path, data_dir)
    _import(build_ozon_search_visibility_workbook(cluster="other cluster"), db_path, data_dir)
    _import(build_ozon_search_visibility_workbook(time="03:56 +00"), db_path, data_dir)
    with transaction(db_path) as conn:
        assert [row[0] for row in conn.execute("SELECT revision FROM search_visibility_snapshots ORDER BY id")] == [1, 1, 1, 1]


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 8, 18, 12, 34, 56, 123456, tzinfo=timezone.utc)


def test_collision_and_post_reservation_failure_compensate_without_mutation(monkeypatch, tmp_path):
    db_path, data_dir = _setup(tmp_path); payload = build_ozon_search_visibility_workbook()
    monkeypatch.setattr(service, "datetime", _FixedDateTime)
    name = f"20260818T123456123456Z-{sha256(payload).hexdigest()}.xlsx"
    target = data_dir / "imports" / name; target.parent.mkdir(); target.write_bytes(b"sentinel")
    with pytest.raises(OzonSearchVisibilityImportFailure) as collision:
        _import(payload, db_path, data_dir)
    assert isinstance(collision.value.error, SearchVisibilityImportPersistenceError)
    assert target.read_bytes() == b"sentinel"
    target.unlink()
    monkeypatch.setattr(SearchVisibilitySnapshotRepository, "resolve_revision",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("injected")))
    with pytest.raises(OzonSearchVisibilityImportFailure) as failed:
        _import(payload, db_path, data_dir)
    assert failed.value.result.status is ImportStatus.FAILED
    assert failed.value.result.source_artifact.stored_relpath is None
    assert not target.exists()
    with transaction(db_path) as conn:
        assert conn.execute("SELECT count(*) FROM products").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM search_queries").fetchone()[0] == 0


def test_recovery_is_cross_kind_safe_and_deletes_only_owned_patterns(tmp_path):
    db_path, data_dir = _setup(tmp_path); imports = data_dir / "imports"; imports.mkdir()
    pr3_name = "20260818T123456123456Z-" + "a" * 64 + ".xlsx"
    pr4_name = "20260818T123456123457Z-" + "b" * 64 + ".xlsx"
    orphan = "20260818T123456123458Z-" + "c" * 64 + ".xlsx"
    with transaction(db_path) as conn:
        lineage = LineageRepository(conn)
        pr3 = lineage.create_import_batch(source="ozon", import_kind="ozon_products_xlsx")
        pr4 = lineage.create_import_batch(source="ozon", import_kind="ozon_search_visibility_xlsx")
        lineage.add_source_artifact(pr3.id, artifact_kind="x", original_name="x", content_sha256="a"*64, byte_size=1, stored_relpath=f"imports/{pr3_name}")
        lineage.add_source_artifact(pr4.id, artifact_kind="x", original_name="x", content_sha256="b"*64, byte_size=1, stored_relpath=f"imports/{pr4_name}")
    for name in (pr3_name, pr4_name, orphan, "manual.xlsx", ".upload-stale.part"):
        (imports / name).write_bytes(b"x")
    service.recover_interrupted_ozon_search_visibility_imports(db_path=db_path, data_dir=data_dir)
    with transaction(db_path) as conn:
        assert LineageRepository(conn).get_import_batch(pr3.id).status is ImportStatus.RUNNING
        assert LineageRepository(conn).get_import_batch(pr4.id).status is ImportStatus.FAILED
    assert (imports / pr3_name).exists() and (imports / pr4_name).exists()
    assert (imports / "manual.xlsx").exists()
    assert not (imports / orphan).exists() and not (imports / ".upload-stale.part").exists()
