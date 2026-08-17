from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import inspect
import re

import pytest

import backend.application.ozon_products_import as service
from backend.domain.lineage import ImportStatus, InvalidImportStatusTransition
from backend.domain.product_snapshot import (
    ConcurrentImportConflict,
    ImportPersistenceError,
    InvalidMetricValue,
    OzonProductsImportFailure,
    UploadTooLarge,
    UnsupportedWorkbook,
)
from backend.ingestion.ozon_products_xlsx import parse_ozon_products_xlsx
from backend.persistence.connection import transaction
from backend.persistence.database import initialize_database
from backend.persistence.repositories.lineage import LineageRepository
from backend.persistence.repositories.product_snapshots import ProductSnapshotRepository
from backend.persistence.repositories.products import ProductRepository
from tests.xlsx_factory import OZON_PRODUCTS_HEADERS, _default_row, build_ozon_products_workbook


def _setup(tmp_path):
    db_path = tmp_path / "scoz.db"
    initialize_database(db_path)
    return db_path, tmp_path


def _import(data, db_path, data_dir, name="report.xlsx"):
    return service.import_ozon_products_xlsx(
        upload=BytesIO(data), original_name=name, db_path=db_path, data_dir=data_dir
    )


def _summaries(db_path):
    with transaction(db_path) as conn:
        return LineageRepository(conn).list_ozon_products_imports(limit=100, offset=0)


def _snapshots(db_path):
    with transaction(db_path) as conn:
        return conn.execute("SELECT * FROM product_snapshots ORDER BY id").fetchall()


def test_finish_ozon_products_import_has_frozen_signature_and_transition(tmp_path):
    signature = inspect.signature(LineageRepository.finish_ozon_products_import)
    assert list(signature.parameters) == ["self", "batch_id", "status", "report_generated_on", "report_window_days", "rows_seen", "rows_accepted", "rows_skipped", "duplicate_observations", "new_observations", "corrected_revisions", "warnings_count", "row_errors_total"]
    assert all(parameter.default is inspect.Parameter.empty for parameter in signature.parameters.values())
    db_path, _ = _setup(tmp_path)
    fields = dict(report_generated_on=None, report_window_days=None, rows_seen=0, rows_accepted=0, rows_skipped=0, duplicate_observations=0, new_observations=0, corrected_revisions=0, warnings_count=0, row_errors_total=0)
    with transaction(db_path) as conn:
        repo = LineageRepository(conn)
        batch = repo.create_import_batch(source="ozon", import_kind="ozon_products_xlsx")
        assert repo.finish_ozon_products_import(batch.id, status=ImportStatus.SUCCESS, **fields).status is ImportStatus.SUCCESS
        with pytest.raises(InvalidImportStatusTransition): repo.finish_ozon_products_import(batch.id, status=ImportStatus.FAILED, **fields)
        running = repo.create_import_batch(source="ozon", import_kind="ozon_products_xlsx")
        with pytest.raises(ValueError, match="non-negative"):
            repo.finish_ozon_products_import(running.id, status=ImportStatus.FAILED, **(fields | {"rows_seen": -1}))


def test_parser_reads_valid_xlsx_from_part_staging_path(tmp_path):
    path = tmp_path / ".upload-00000000-0000-4000-8000-000000000000.part"
    path.write_bytes(build_ozon_products_workbook())
    report = parse_ozon_products_xlsx(path)
    assert report.rows_seen == 1
    assert report.rows[0].ozon_product_id == "100000001"


@pytest.mark.parametrize(
    ("original", "expected"),
    [
        ("report.xlsx", "report.xlsx"),
        ("/tmp/report.xlsx", "report.xlsx"),
        ("../../secret/report.xlsx", "report.xlsx"),
        (r"C:\Users\User\report.xlsx", "report.xlsx"),
        (r"..\..\report.xlsx", "report.xlsx"),
        (r"\\server\share\report.xlsx", "report.xlsx"),
        ("", "upload.xlsx"),
        (".", "upload.xlsx"),
        ("..", "upload.xlsx"),
    ],
)
def test_safe_original_basename(original, expected):
    assert service.safe_original_basename(original) == expected


def test_stream_limit_staging_hash_size_and_fsync(monkeypatch, tmp_path):
    db_path, data_dir = _setup(tmp_path)
    fsync_calls = []
    monkeypatch.setattr(service.os, "fsync", lambda fd: fsync_calls.append(fd))
    payload = b"x" * service.MAX_UPLOAD_BYTES
    with pytest.raises(OzonProductsImportFailure) as caught:
        _import(payload, db_path, data_dir)
    assert isinstance(caught.value.error, UnsupportedWorkbook)
    summary = _summaries(db_path)[0]
    assert summary.source_artifact.byte_size == service.MAX_UPLOAD_BYTES
    assert summary.source_artifact.content_sha256 == sha256(payload).hexdigest()
    assert fsync_calls
    assert not list((data_dir / "imports").glob(".upload-*.part"))

    with pytest.raises(OzonProductsImportFailure) as too_large:
        _import(payload + b"x", db_path, data_dir)
    assert isinstance(too_large.value.error, UploadTooLarge)
    assert too_large.value.result is None
    assert len(_summaries(db_path)) == 1
    assert not list((data_dir / "imports").glob(".upload-*.part"))


def test_staging_name_and_exclusive_creation_contract(monkeypatch, tmp_path):
    db_path, data_dir = _setup(tmp_path)
    real_parser = service.parse_ozon_products_xlsx
    observed = {}

    def inspect_staging(path):
        observed["name"] = path.name
        observed["bytes"] = path.read_bytes()
        return real_parser(path)

    monkeypatch.setattr(service, "parse_ozon_products_xlsx", inspect_staging)
    payload = build_ozon_products_workbook()
    _import(payload, db_path, data_dir)
    assert re.fullmatch(
        r"\.upload-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.part",
        observed["name"],
    )
    assert observed["bytes"] == payload

def test_success_persists_identity_snapshot_and_archive(tmp_path):
    db_path, data_dir = _setup(tmp_path)
    result = _import(build_ozon_products_workbook(), db_path, data_dir)
    assert result.status is ImportStatus.SUCCESS
    assert (result.rows_seen, result.rows_accepted, result.rows_skipped) == (1, 1, 0)
    assert (result.new_observations, result.corrected_revisions) == (1, 0)
    assert result.readiness == "SELECT_OWN_PRODUCTS"
    assert result.source_artifact.stored_relpath is not None
    assert (data_dir / result.source_artifact.stored_relpath).is_file()
    assert not list((data_dir / "imports").glob(".upload-*.part"))
    with transaction(db_path) as conn:
        product = ProductRepository(conn).find_by_external_identity(
            source="ozon", identity_type="ozon_product_id",
            identity_value="100000001", source_account_scope="",
        )
        assert product is not None
        snapshot = ProductSnapshotRepository(conn).list_latest_current_for_products(limit=100, offset=0)[0]
        assert snapshot is not None and snapshot.revision == 1


def test_partial_success_retains_archive_and_valid_row(tmp_path):
    db_path, data_dir = _setup(tmp_path)
    valid = _default_row("Синтетическая категория")
    invalid = dict(valid)
    invalid[OZON_PRODUCTS_HEADERS[1]] = "bad"
    result = _import(build_ozon_products_workbook(rows=[valid, invalid]), db_path, data_dir)
    assert result.status is ImportStatus.PARTIAL_SUCCESS
    assert (result.rows_seen, result.rows_accepted, result.rows_skipped) == (2, 1, 1)
    assert result.row_errors_total == 1
    assert result.row_errors[0].row == 8
    assert result.row_errors[0].code == "InvalidProductIdentity"
    assert result.row_errors[0].message == "Некорректная ссылка на товар."
    assert (data_dir / result.source_artifact.stored_relpath).is_file()
    assert len(_snapshots(db_path)) == 1


def test_zero_usable_rows_fails_without_archive_or_mutation(tmp_path):
    db_path, data_dir = _setup(tmp_path)
    invalid = _default_row("Синтетическая категория")
    invalid[OZON_PRODUCTS_HEADERS[1]] = "bad"
    with pytest.raises(OzonProductsImportFailure) as caught:
        _import(build_ozon_products_workbook(rows=[invalid]), db_path, data_dir)
    assert isinstance(caught.value.error, InvalidMetricValue)
    assert caught.value.result.status is ImportStatus.FAILED
    assert caught.value.result.source_artifact.stored_relpath is None
    assert not _snapshots(db_path)
    assert not list((data_dir / "imports").iterdir())


def test_duplicate_correction_date_and_window_revision_matrix(tmp_path):
    db_path, data_dir = _setup(tmp_path)
    base = _default_row("Синтетическая категория")
    first = _import(build_ozon_products_workbook(rows=[base]), db_path, data_dir)
    duplicate = _import(build_ozon_products_workbook(rows=[base]), db_path, data_dir)
    changed = dict(base); changed[OZON_PRODUCTS_HEADERS[0]] = "Changed"
    correction = _import(build_ozon_products_workbook(rows=[changed]), db_path, data_dir)
    different_date = _import(build_ozon_products_workbook(rows=[changed], generated_on="08.17.26"), db_path, data_dir)
    different_window = _import(build_ozon_products_workbook(rows=[changed], window_label="28 дней"), db_path, data_dir)
    assert first.new_observations == 1
    assert duplicate.duplicate_observations == 1
    assert correction.corrected_revisions == 1
    assert different_date.new_observations == 1
    assert different_window.new_observations == 1
    snapshots = _snapshots(db_path)
    assert [row["revision"] for row in snapshots] == [1, 2, 1, 1]
    assert snapshots[1]["supersedes_snapshot_id"] == snapshots[0]["id"]
    assert snapshots[0]["title"] == "Синтетический товар"


def test_in_file_duplicates_warn_without_partial_success_and_conflicts_are_fatal(tmp_path):
    db_path, data_dir = _setup(tmp_path)
    row = _default_row("Синтетическая категория")
    result = _import(build_ozon_products_workbook(rows=[row, row]), db_path, data_dir)
    assert result.status is ImportStatus.SUCCESS
    assert result.rows_accepted == 1 and result.duplicate_observations == 1
    assert result.warnings_count >= 1

    conflict = dict(row); conflict[OZON_PRODUCTS_HEADERS[0]] = "Changed"
    with pytest.raises(OzonProductsImportFailure) as caught:
        _import(build_ozon_products_workbook(rows=[row, conflict]), db_path, data_dir)
    assert type(caught.value.error).__name__ == "ConflictingObservationRows"
    assert len(_snapshots(db_path)) == 1


def test_row_error_cap_is_ordered(tmp_path):
    db_path, data_dir = _setup(tmp_path)
    rows = [_default_row("Синтетическая категория")]
    for index in range(51):
        row = _default_row("Синтетическая категория")
        row[OZON_PRODUCTS_HEADERS[1]] = f"bad-{index}"
        rows.append(row)
    result = _import(build_ozon_products_workbook(rows=rows), db_path, data_dir)
    assert result.row_errors_total == 51
    assert len(result.row_errors) == 50 and result.row_errors_truncated is True
    assert [error.row for error in result.row_errors] == list(range(8, 58))


def test_nonblocking_lock_has_no_side_effect_and_releases_after_terminal_paths(tmp_path):
    db_path, data_dir = _setup(tmp_path)
    service._IMPORT_LOCK.acquire()
    try:
        with pytest.raises(OzonProductsImportFailure) as caught:
            _import(build_ozon_products_workbook(), db_path, data_dir)
        assert isinstance(caught.value.error, ConcurrentImportConflict)
        assert caught.value.result is None
        assert not (data_dir / "imports").exists()
        assert not _summaries(db_path)
    finally:
        service._IMPORT_LOCK.release()
    assert _import(build_ozon_products_workbook(), db_path, data_dir).status is ImportStatus.SUCCESS
    with pytest.raises(OzonProductsImportFailure):
        _import(b"bad", db_path, data_dir)
    assert _import(build_ozon_products_workbook(), db_path, data_dir).status is ImportStatus.SUCCESS


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 8, 16, 12, 34, 56, 123456, tzinfo=timezone.utc)


def test_archive_collision_preserves_existing_file(monkeypatch, tmp_path):
    db_path, data_dir = _setup(tmp_path)
    payload = build_ozon_products_workbook()
    monkeypatch.setattr(service, "datetime", _FixedDateTime)
    name = f"20260816T123456123456Z-{sha256(payload).hexdigest()}.xlsx"
    destination = data_dir / "imports" / name
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"sentinel")
    with pytest.raises(OzonProductsImportFailure) as caught:
        _import(payload, db_path, data_dir)
    assert isinstance(caught.value.error, ImportPersistenceError)
    assert destination.read_bytes() == b"sentinel"
    assert caught.value.result.status is ImportStatus.FAILED
    assert caught.value.result.source_artifact.stored_relpath is None
    assert not _snapshots(db_path)
    assert not list(destination.parent.glob(".upload-*.part"))


def test_failure_after_archive_reservation_compensates(monkeypatch, tmp_path):
    db_path, data_dir = _setup(tmp_path)
    monkeypatch.setattr(
        ProductSnapshotRepository, "resolve_revision",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("injected")),
    )
    with pytest.raises(OzonProductsImportFailure) as caught:
        _import(build_ozon_products_workbook(), db_path, data_dir)
    assert isinstance(caught.value.error, ImportPersistenceError)
    assert caught.value.result.status is ImportStatus.FAILED
    assert caught.value.result.source_artifact.stored_relpath is None
    assert not _snapshots(db_path)
    assert not list((data_dir / "imports").iterdir())


def test_recovery_preserves_metadata_and_deletes_only_owned_patterns(tmp_path):
    db_path, data_dir = _setup(tmp_path)
    imports = data_dir / "imports"; imports.mkdir()
    referenced_name = "20260816T123456123456Z-" + "a" * 64 + ".xlsx"
    orphan_name = "20260816T123456123457Z-" + "b" * 64 + ".xlsx"
    with transaction(db_path) as conn:
        lineage = LineageRepository(conn)
        batch = lineage.create_import_batch(source="ozon", import_kind="ozon_products_xlsx")
        artifact = lineage.add_source_artifact(
            batch.id, artifact_kind="ozon_products_xlsx", original_name="report.xlsx",
            content_sha256="a" * 64, byte_size=123,
            stored_relpath=f"imports/{referenced_name}",
        )
        conn.execute(
            "UPDATE import_batches SET report_generated_on='2026-08-16',report_window_days=7,rows_seen=9 WHERE id=?",
            (batch.id,),
        )
    for name in (referenced_name, orphan_name, "arbitrary.xlsx", ".upload-one.part", ".upload-two.part", "20260816T123456Z-" + "c" * 64 + ".xlsx"):
        (imports / name).write_bytes(name.encode())
    (imports / ".upload-directory.part").mkdir()
    service.recover_interrupted_ozon_products_imports(db_path=db_path, data_dir=data_dir)
    summary = _summaries(db_path)[0]
    assert summary.status is ImportStatus.FAILED and summary.finished_at is not None
    assert summary.report_generated_on.isoformat() == "2026-08-16"
    assert summary.report_window_days == 7 and summary.rows_seen == 9
    assert (imports / referenced_name).exists()
    assert not (imports / orphan_name).exists()
    assert (imports / "arbitrary.xlsx").exists()
    assert (imports / ("20260816T123456Z-" + "c" * 64 + ".xlsx")).exists()
    assert (imports / ".upload-directory.part").is_dir()
    assert not list(imports.glob(".upload-one.part"))
