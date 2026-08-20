from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO
import sqlite3
import uuid
from zipfile import BadZipFile

from backend.application.import_runtime import (
    ARCHIVE_RE, IMPORT_LOCK, MAX_ROW_ERRORS, XlsxUploadTooLarge,
    XlsxUploadUnsupportedMediaType, publish_staged_archive, stage_xlsx_upload,
)
from backend.config import DATA_DIR
from backend.domain.lineage import ImportStatus
from backend.domain.product_snapshot import SnapshotWriteKind
from backend.domain.query_metric import (
    OzonQueryMetricsError, OzonQueryMetricsImportFailure,
    OzonQueryMetricsImportResult, QueryMetricsConcurrentImportConflict,
    QueryMetricsImportPersistenceError, QueryMetricsNoUsableRows,
    QueryMetricsUnsupportedUploadMediaType, QueryMetricsUnsupportedWorkbook,
    QueryMetricsUploadTooLarge,
)
from backend.ingestion.ozon_query_metrics_xlsx import parse_ozon_query_metrics_xlsx
from backend.ingestion.ozon_query_metrics_xlsx_compat import prepare_query_metrics_read_copy
from backend.persistence.connection import transaction
from backend.persistence.repositories.lineage import LineageRepository
from backend.persistence.repositories.query_metric_snapshots import QueryMetricSnapshotRepository
from backend.persistence.repositories.search_dimensions import SearchDimensionRepository


def _result(summary, errors=()) -> OzonQueryMetricsImportResult:
    assert summary.source_artifact is not None
    return OzonQueryMetricsImportResult(
        summary.import_batch_id, "OZON_QUERY_METRICS", summary.status,
        summary.period_start, summary.period_end, summary.sort_context,
        summary.rows_seen, summary.rows_accepted, summary.rows_skipped,
        summary.duplicate_observations, summary.new_observations,
        summary.corrected_revisions, summary.warnings_count,
        summary.row_errors_total, tuple(errors[:MAX_ROW_ERRORS]),
        len(errors) > MAX_ROW_ERRORS, summary.source_artifact,
        summary.finished_at or summary.started_at,
    )


def _finish_failed(*, db_path, batch_id, report=None):
    try:
        with transaction(db_path) as conn:
            summary = LineageRepository(conn).finish_ozon_query_metrics_import(
                batch_id, status=ImportStatus.FAILED,
                period_start=None if report is None else report.period_start,
                period_end=None if report is None else report.period_end,
                sort_context=None if report is None else report.sort_context,
                rows_seen=0 if report is None else report.rows_seen,
                rows_accepted=0 if report is None else len(report.rows),
                rows_skipped=0 if report is None else len(report.row_errors),
                duplicate_observations=0 if report is None else report.duplicate_input_rows,
                new_observations=0, corrected_revisions=0,
                warnings_count=0 if report is None else report.warnings_count,
                row_errors_total=0 if report is None else len(report.row_errors))
        return _result(summary, () if report is None else report.row_errors)
    except Exception:
        return None


def import_ozon_query_metrics_xlsx(*, upload: BinaryIO, original_name: str,
        db_path: Path | None = None, data_dir: Path = DATA_DIR) -> OzonQueryMetricsImportResult:
    if not IMPORT_LOCK.acquire(blocking=False):
        raise OzonQueryMetricsImportFailure(
            error=QueryMetricsConcurrentImportConflict(), result=None)
    staged = final_path = read_copy = None
    final_owned = False
    batch_id = artifact_id = None
    report = None
    cleanup_error = None
    try:
        try:
            staged = stage_xlsx_upload(upload=upload, original_name=original_name,
                                       data_dir=data_dir)
        except XlsxUploadUnsupportedMediaType as error:
            raise OzonQueryMetricsImportFailure(
                error=QueryMetricsUnsupportedUploadMediaType(), result=None) from error
        except XlsxUploadTooLarge as error:
            raise OzonQueryMetricsImportFailure(
                error=QueryMetricsUploadTooLarge(), result=None) from error
        except OSError as error:
            raise OzonQueryMetricsImportFailure(
                error=QueryMetricsImportPersistenceError(), result=None) from error
        try:
            with transaction(db_path) as conn:
                lineage = LineageRepository(conn)
                batch = lineage.create_import_batch(source="ozon", import_kind="ozon_query_metrics_xlsx")
                artifact = lineage.add_source_artifact(
                    batch.id, artifact_kind="ozon_query_metrics_xlsx",
                    original_name=staged.original_name, content_sha256=staged.sha256,
                    byte_size=staged.byte_size)
            batch_id, artifact_id = batch.id, artifact.id
        except (sqlite3.Error, OSError) as error:
            raise OzonQueryMetricsImportFailure(
                error=QueryMetricsImportPersistenceError(), result=None) from error
        read_copy = data_dir / "imports" / f".readcopy-{uuid.uuid4()}.xlsx"
        try:
            prepare_query_metrics_read_copy(staged.staged_path, read_copy)
        except (BadZipFile, KeyError, ValueError) as error:
            result = _finish_failed(db_path=db_path, batch_id=batch_id)
            raise OzonQueryMetricsImportFailure(
                error=QueryMetricsUnsupportedWorkbook(), result=result) from error
        except OSError as error:
            result = _finish_failed(db_path=db_path, batch_id=batch_id)
            raise OzonQueryMetricsImportFailure(
                error=QueryMetricsImportPersistenceError(), result=result) from error
        try:
            report = parse_ozon_query_metrics_xlsx(read_copy)
        except OzonQueryMetricsError as error:
            result = _finish_failed(db_path=db_path, batch_id=batch_id)
            raise OzonQueryMetricsImportFailure(error=error, result=result) from error
        finally:
            if read_copy is not None:
                try:
                    read_copy.unlink(missing_ok=True)
                    read_copy = None
                except OSError as error:
                    cleanup_error = error
        if cleanup_error is not None:
            result = _finish_failed(db_path=db_path, batch_id=batch_id, report=report)
            raise OzonQueryMetricsImportFailure(
                error=QueryMetricsImportPersistenceError(), result=result) from cleanup_error
        if not report.rows:
            result = _finish_failed(db_path=db_path, batch_id=batch_id, report=report)
            raise OzonQueryMetricsImportFailure(error=QueryMetricsNoUsableRows(), result=result)
        imported_at = datetime.now(timezone.utc)
        try:
            final_path, stored_relpath = publish_staged_archive(
                staged, data_dir=data_dir, imported_at=imported_at)
            staged = None
            final_owned = True
            with transaction(db_path) as conn:
                lineage = LineageRepository(conn)
                lineage.set_source_artifact_stored_relpath(artifact_id, stored_relpath)
                dimensions = SearchDimensionRepository(conn)
                snapshots = QueryMetricSnapshotRepository(conn)
                duplicate = report.duplicate_input_rows
                new = corrected = 0
                for row in report.rows:
                    query = dimensions.resolve_search_query(row.query_text)
                    write = snapshots.resolve_revision(
                        search_query_id=query.id, period_start=report.period_start,
                        period_end=report.period_end, payload_sha256=row.payload_sha256,
                        import_batch_id=batch_id, source_artifact_id=artifact_id,
                        imported_at=imported_at, snapshot_values=row.snapshot_values)
                    if write.kind is SnapshotWriteKind.DUPLICATE:
                        duplicate += 1
                    elif write.kind is SnapshotWriteKind.NEW:
                        new += 1
                    else:
                        corrected += 1
                status = ImportStatus.PARTIAL_SUCCESS if report.row_errors else ImportStatus.SUCCESS
                summary = lineage.finish_ozon_query_metrics_import(
                    batch_id, status=status, period_start=report.period_start,
                    period_end=report.period_end, sort_context=report.sort_context,
                    rows_seen=report.rows_seen, rows_accepted=len(report.rows),
                    rows_skipped=len(report.row_errors), duplicate_observations=duplicate,
                    new_observations=new, corrected_revisions=corrected,
                    warnings_count=report.warnings_count,
                    row_errors_total=len(report.row_errors))
            return _result(summary, report.row_errors)
        except (sqlite3.Error, OSError) as error:
            if final_owned and final_path is not None:
                try:
                    final_path.unlink(missing_ok=True)
                except OSError:
                    pass
            result = _finish_failed(db_path=db_path, batch_id=batch_id, report=report)
            raise OzonQueryMetricsImportFailure(
                error=QueryMetricsImportPersistenceError(), result=result) from error
        except Exception:
            if final_owned and final_path is not None:
                try:
                    final_path.unlink(missing_ok=True)
                except OSError:
                    pass
            _finish_failed(db_path=db_path, batch_id=batch_id, report=report)
            raise
    except OzonQueryMetricsImportFailure:
        raise
    except Exception:
        if batch_id is not None:
            _finish_failed(db_path=db_path, batch_id=batch_id, report=report)
        raise
    finally:
        if read_copy is not None:
            try:
                read_copy.unlink(missing_ok=True)
            except OSError:
                pass
        if staged is not None:
            try:
                staged.staged_path.unlink(missing_ok=True)
            except OSError:
                pass
        IMPORT_LOCK.release()


def recover_interrupted_ozon_query_metrics_imports(*, db_path: Path | None = None,
        data_dir: Path = DATA_DIR) -> None:
    with transaction(db_path) as conn:
        lineage = LineageRepository(conn)
        lineage.fail_running_ozon_query_metrics_imports(finished_at=datetime.now(timezone.utc))
        referenced = lineage.list_referenced_archive_paths()
    imports = data_dir / "imports"
    if not imports.exists():
        return
    for path in imports.iterdir():
        temporary = ((path.name.startswith(".upload-") and path.suffix == ".part")
                     or (path.name.startswith(".readcopy-") and path.suffix == ".xlsx"))
        orphan = ARCHIVE_RE.fullmatch(path.name) and f"imports/{path.name}" not in referenced
        if path.is_file() and (temporary or orphan):
            path.unlink()
