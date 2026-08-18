import hashlib
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from backend.application.import_runtime import (
    ARCHIVE_RE, IMPORT_LOCK, MAX_ROW_ERRORS, MAX_UPLOAD_BYTES, safe_original_basename,
)
from backend.config import DATA_DIR
from backend.domain.lineage import ImportStatus
from backend.domain.product_snapshot import SnapshotWriteKind
from backend.domain.search_visibility import (
    OzonSearchVisibilityError, OzonSearchVisibilityImportFailure,
    OzonSearchVisibilityImportResult, SearchVisibilityConcurrentImportConflict,
    SearchVisibilityImportPersistenceError, SearchVisibilityNoUsableRows,
    SearchVisibilityUnsupportedUploadMediaType, SearchVisibilityUploadTooLarge,
)
from backend.ingestion.ozon_search_visibility_xlsx import parse_ozon_search_visibility_xlsx
from backend.persistence.connection import transaction
from backend.persistence.repositories.lineage import LineageRepository
from backend.persistence.repositories.products import ProductRepository
from backend.persistence.repositories.search_dimensions import SearchDimensionRepository
from backend.persistence.repositories.search_visibility_snapshots import SearchVisibilitySnapshotRepository


def _result(summary, errors=()) -> OzonSearchVisibilityImportResult:
    assert summary.source_artifact is not None
    return OzonSearchVisibilityImportResult(
        summary.import_batch_id, "OZON_SEARCH_VISIBILITY", summary.status,
        summary.observed_at, summary.query_text, summary.cluster_name,
        summary.declared_rows, summary.rows_seen, summary.rows_accepted,
        summary.rows_skipped, summary.duplicate_observations,
        summary.new_observations, summary.corrected_revisions,
        summary.warnings_count, summary.row_errors_total,
        tuple(errors[:MAX_ROW_ERRORS]), len(errors) > MAX_ROW_ERRORS,
        summary.source_artifact, summary.finished_at or summary.started_at,
    )


def _finish_failed(*, db_path: Path | None, batch_id: int, report=None):
    """Best-effort durable compensation for a RUNNING import batch."""
    try:
        with transaction(db_path) as conn:
            summary = LineageRepository(conn).finish_ozon_search_visibility_import(
                batch_id, status=ImportStatus.FAILED,
                observed_at=None if report is None else report.observed_at,
                query_text=None if report is None else report.query_text,
                cluster_name=None if report is None else report.cluster_name,
                declared_rows=None if report is None else report.declared_rows,
                rows_seen=0 if report is None else report.rows_seen,
                rows_accepted=0 if report is None else len(report.rows),
                rows_skipped=0 if report is None else len(report.row_errors),
                duplicate_observations=0 if report is None else report.duplicate_input_rows,
                new_observations=0, corrected_revisions=0,
                warnings_count=0 if report is None else report.warnings_count,
                row_errors_total=0 if report is None else len(report.row_errors),
            )
        return _result(summary, () if report is None else report.row_errors)
    except Exception:
        return None


def import_ozon_search_visibility_xlsx(*, upload: BinaryIO, original_name: str,
                                       db_path: Path | None = None,
                                       data_dir: Path = DATA_DIR) -> OzonSearchVisibilityImportResult:
    if not IMPORT_LOCK.acquire(blocking=False):
        raise OzonSearchVisibilityImportFailure(
            error=SearchVisibilityConcurrentImportConflict(), result=None
        )
    staged_path: Path | None = None
    final_path: Path | None = None
    final_owned = False
    batch_id: int | None = None
    artifact_id: int | None = None
    try:
        original = safe_original_basename(original_name)
        if not original.lower().endswith(".xlsx"):
            raise OzonSearchVisibilityImportFailure(
                error=SearchVisibilityUnsupportedUploadMediaType(), result=None
            )
        try:
            imports_dir = data_dir / "imports"
            imports_dir.mkdir(parents=True, exist_ok=True)
            staged_path = imports_dir / f".upload-{uuid.uuid4()}.part"
            digest = hashlib.sha256()
            size = 0
            with staged_path.open("xb") as target:
                while chunk := upload.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise SearchVisibilityUploadTooLarge()
                    digest.update(chunk)
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
        except SearchVisibilityUploadTooLarge as error:
            staged_path.unlink(missing_ok=True)
            staged_path = None
            raise OzonSearchVisibilityImportFailure(error=error, result=None) from error
        except OSError as error:
            raise OzonSearchVisibilityImportFailure(
                error=SearchVisibilityImportPersistenceError(), result=None
            ) from error
        sha256 = digest.hexdigest()
        try:
            with transaction(db_path) as conn:
                lineage = LineageRepository(conn)
                batch = lineage.create_import_batch(
                    source="ozon", import_kind="ozon_search_visibility_xlsx"
                )
                artifact = lineage.add_source_artifact(
                    batch.id, artifact_kind="ozon_search_visibility_xlsx",
                    original_name=original, content_sha256=sha256, byte_size=size,
                )
            batch_id = batch.id
            artifact_id = artifact.id
        except Exception as error:
            raise OzonSearchVisibilityImportFailure(
                error=SearchVisibilityImportPersistenceError(), result=None
            ) from error
        try:
            report = parse_ozon_search_visibility_xlsx(staged_path)
        except OzonSearchVisibilityError as error:
            staged_path.unlink(missing_ok=True)
            staged_path = None
            try:
                with transaction(db_path) as conn:
                    summary = LineageRepository(conn).finish_ozon_search_visibility_import(
                        batch_id, status=ImportStatus.FAILED, observed_at=None,
                        query_text=None, cluster_name=None, declared_rows=None,
                        rows_seen=0, rows_accepted=0, rows_skipped=0,
                        duplicate_observations=0, new_observations=0,
                        corrected_revisions=0, warnings_count=0, row_errors_total=0,
                    )
            except Exception as persistence_error:
                result = _finish_failed(db_path=db_path, batch_id=batch_id)
                raise OzonSearchVisibilityImportFailure(
                    error=SearchVisibilityImportPersistenceError(), result=result
                ) from persistence_error
            raise OzonSearchVisibilityImportFailure(error=error, result=_result(summary)) from error
        except Exception:
            try:
                staged_path.unlink(missing_ok=True)
            except OSError:
                pass
            staged_path = None
            _finish_failed(db_path=db_path, batch_id=batch_id)
            raise
        if not report.rows:
            staged_path.unlink(missing_ok=True)
            staged_path = None
            try:
                with transaction(db_path) as conn:
                    summary = LineageRepository(conn).finish_ozon_search_visibility_import(
                        batch_id, status=ImportStatus.FAILED, observed_at=report.observed_at,
                        query_text=report.query_text, cluster_name=report.cluster_name,
                        declared_rows=report.declared_rows, rows_seen=report.rows_seen,
                        rows_accepted=0, rows_skipped=len(report.row_errors),
                        duplicate_observations=report.duplicate_input_rows,
                        new_observations=0, corrected_revisions=0,
                        warnings_count=report.warnings_count,
                        row_errors_total=len(report.row_errors),
                    )
            except Exception as error:
                result = _finish_failed(db_path=db_path, batch_id=batch_id, report=report)
                raise OzonSearchVisibilityImportFailure(
                    error=SearchVisibilityImportPersistenceError(), result=result
                ) from error
            raise OzonSearchVisibilityImportFailure(
                error=SearchVisibilityNoUsableRows(), result=_result(summary, report.row_errors)
            )
        try:
            imported_at = datetime.now(timezone.utc)
            filename = f"{imported_at.strftime('%Y%m%dT%H%M%S%fZ')}-{sha256}.xlsx"
            final_path = imports_dir / filename
            try:
                with final_path.open("xb"):
                    pass
                final_owned = True
            except FileExistsError as error:
                raise SearchVisibilityImportPersistenceError("generated archive collision") from error
            staged_path.replace(final_path)
            staged_path = None
            with transaction(db_path) as conn:
                lineage = LineageRepository(conn)
                lineage.set_source_artifact_stored_relpath(
                    artifact_id, PurePosixPath("imports", filename).as_posix()
                )
                dimensions = SearchDimensionRepository(conn)
                query = dimensions.resolve_search_query(report.query_text)
                cluster = dimensions.resolve_cluster(report.cluster_name)
                products = ProductRepository(conn)
                snapshots = SearchVisibilitySnapshotRepository(conn)
                duplicate = report.duplicate_input_rows
                new = corrected = 0
                for row in report.rows:
                    product = products.resolve_or_create_ozon_product(row.ozon_product_id)
                    write = snapshots.resolve_revision(
                        product_id=product.id, search_query_id=query.id,
                        cluster_id=cluster.id, observed_at=report.observed_at,
                        payload_sha256=row.payload_sha256, import_batch_id=batch_id,
                        source_artifact_id=artifact_id, imported_at=imported_at,
                        snapshot_values=row.snapshot_values,
                    )
                    if write.kind is SnapshotWriteKind.DUPLICATE:
                        duplicate += 1
                    elif write.kind is SnapshotWriteKind.NEW:
                        new += 1
                    else:
                        corrected += 1
                status = ImportStatus.PARTIAL_SUCCESS if report.row_errors else ImportStatus.SUCCESS
                summary = lineage.finish_ozon_search_visibility_import(
                    batch_id, status=status, observed_at=report.observed_at,
                    query_text=report.query_text, cluster_name=report.cluster_name,
                    declared_rows=report.declared_rows, rows_seen=report.rows_seen,
                    rows_accepted=len(report.rows), rows_skipped=len(report.row_errors),
                    duplicate_observations=duplicate, new_observations=new,
                    corrected_revisions=corrected, warnings_count=report.warnings_count,
                    row_errors_total=len(report.row_errors),
                )
            return _result(summary, report.row_errors)
        except Exception as error:
            if staged_path is not None:
                staged_path.unlink(missing_ok=True)
                staged_path = None
            if final_owned and final_path is not None:
                final_path.unlink(missing_ok=True)
                final_owned = False
            result = _finish_failed(db_path=db_path, batch_id=batch_id, report=report)
            raise OzonSearchVisibilityImportFailure(
                error=SearchVisibilityImportPersistenceError(), result=result
            ) from error
    except OzonSearchVisibilityImportFailure:
        raise
    finally:
        if staged_path is not None:
            staged_path.unlink(missing_ok=True)
        IMPORT_LOCK.release()


def recover_interrupted_ozon_search_visibility_imports(*, db_path: Path | None = None,
                                                        data_dir: Path = DATA_DIR) -> None:
    with transaction(db_path) as conn:
        lineage = LineageRepository(conn)
        lineage.fail_running_ozon_search_visibility_imports(finished_at=datetime.now(timezone.utc))
        referenced = lineage.list_referenced_archive_paths()
    imports_dir = data_dir / "imports"
    if not imports_dir.exists():
        return
    for path in imports_dir.iterdir():
        is_stage = path.name.startswith(".upload-") and path.suffix == ".part"
        is_orphan = ARCHIVE_RE.fullmatch(path.name) and f"imports/{path.name}" not in referenced
        if path.is_file() and (is_stage or is_orphan):
            path.unlink()
