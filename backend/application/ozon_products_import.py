import hashlib
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from backend.application.import_runtime import (
    ARCHIVE_RE,
    IMPORT_LOCK,
    MAX_ROW_ERRORS,
    MAX_UPLOAD_BYTES,
    safe_original_basename,
)
from backend.config import DATA_DIR
from backend.domain.lineage import ImportStatus
from backend.domain.product_snapshot import (
    ConcurrentImportConflict, ImportPersistenceError, ImportResult,
    OzonProductsError, OzonProductsImportFailure, SnapshotWriteKind,
    UnsupportedUploadMediaType, UploadTooLarge,
)
from backend.ingestion.ozon_products_xlsx import parse_ozon_products_xlsx
from backend.persistence.connection import transaction
from backend.persistence.repositories.lineage import LineageRepository
from backend.persistence.repositories.product_snapshots import ProductSnapshotRepository
from backend.persistence.repositories.products import ProductRepository

def _result(summary, errors=(), readiness="SELECT_OWN_PRODUCTS") -> ImportResult:
    assert summary.source_artifact is not None
    return ImportResult(summary.import_batch_id,"OZON_PRODUCTS",summary.status,summary.report_generated_on,summary.report_window_days,summary.rows_seen,summary.rows_accepted,summary.rows_skipped,summary.duplicate_observations,summary.new_observations,summary.corrected_revisions,summary.warnings_count,summary.row_errors_total,tuple(errors[:MAX_ROW_ERRORS]),len(errors)>MAX_ROW_ERRORS,summary.source_artifact,summary.finished_at or summary.started_at,readiness)

def import_ozon_products_xlsx(*, upload: BinaryIO, original_name: str, db_path: Path | None = None, data_dir: Path = DATA_DIR) -> ImportResult:
    if not IMPORT_LOCK.acquire(blocking=False):
        raise OzonProductsImportFailure(error=ConcurrentImportConflict(),result=None)
    staged=None; final=None; final_owned=False; batch_id=None
    try:
        original=safe_original_basename(original_name)
        if not original.lower().endswith(".xlsx"):
            raise OzonProductsImportFailure(error=UnsupportedUploadMediaType(),result=None)
        imports_dir=data_dir/"imports"; imports_dir.mkdir(parents=True,exist_ok=True)
        staged=imports_dir/f".upload-{uuid.uuid4()}.part"; digest=hashlib.sha256(); size=0
        with staged.open("xb") as target:
            while chunk := upload.read(1024*1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES: raise UploadTooLarge()
                digest.update(chunk); target.write(chunk)
            target.flush(); os.fsync(target.fileno())
        sha=digest.hexdigest()
        with transaction(db_path) as conn:
            lineage=LineageRepository(conn); batch=lineage.create_import_batch(source="ozon",import_kind="ozon_products_xlsx")
            batch_id=batch.id; artifact=lineage.add_source_artifact(batch.id,artifact_kind="ozon_products_xlsx",original_name=original,content_sha256=sha,byte_size=size)
        try: report=parse_ozon_products_xlsx(staged)
        except OzonProductsError as error:
            staged.unlink(missing_ok=True)
            with transaction(db_path) as conn:
                summary=LineageRepository(conn).finish_ozon_products_import(batch_id,status=ImportStatus.FAILED,report_generated_on=None,report_window_days=None,rows_seen=0,rows_accepted=0,rows_skipped=0,duplicate_observations=0,new_observations=0,corrected_revisions=0,warnings_count=0,row_errors_total=0)
            raise OzonProductsImportFailure(error=error,result=_result(summary))
        try:
            now=datetime.now(timezone.utc); filename=f"{now.strftime('%Y%m%dT%H%M%S%fZ')}-{sha}.xlsx"; final=imports_dir/filename
            try:
                with final.open("xb"):
                    pass
                final_owned=True
            except FileExistsError as error:
                raise ImportPersistenceError("generated archive collision") from error
            staged.replace(final); staged=None
            with transaction(db_path) as conn:
                lineage=LineageRepository(conn); lineage.set_source_artifact_stored_relpath(artifact.id,PurePosixPath("imports",filename).as_posix())
                products=ProductRepository(conn); snapshots=ProductSnapshotRepository(conn); duplicate=report.duplicate_input_rows; new=corrected=0
                for row in report.rows:
                    product=products.resolve_or_create_ozon_product(row.ozon_product_id)
                    write=snapshots.resolve_revision(product_id=product.id,report_generated_on=report.report_generated_on,report_window_days=report.report_window_days,payload_sha256=row.payload_sha256,import_batch_id=batch_id,source_artifact_id=artifact.id,imported_at=now,snapshot_values=row.snapshot_values)
                    if write.kind is SnapshotWriteKind.DUPLICATE: duplicate += 1
                    elif write.kind is SnapshotWriteKind.NEW: new += 1
                    else: corrected += 1
                status=ImportStatus.PARTIAL_SUCCESS if report.row_errors else ImportStatus.SUCCESS
                summary=lineage.finish_ozon_products_import(batch_id,status=status,report_generated_on=report.report_generated_on,report_window_days=report.report_window_days,rows_seen=report.rows_seen,rows_accepted=len(report.rows),rows_skipped=len(report.row_errors),duplicate_observations=duplicate,new_observations=new,corrected_revisions=corrected,warnings_count=report.warnings_count,row_errors_total=len(report.row_errors))
                readiness="READY" if products.any_owned() else "SELECT_OWN_PRODUCTS"
            return _result(summary,report.row_errors,readiness)
        except Exception as error:
            if staged is not None:
                staged.unlink(missing_ok=True)
                staged = None
            if final_owned and final is not None:
                final.unlink(missing_ok=True)
                final_owned = False
            with transaction(db_path) as conn:
                summary=LineageRepository(conn).finish_ozon_products_import(batch_id,status=ImportStatus.FAILED,report_generated_on=report.report_generated_on,report_window_days=report.report_window_days,rows_seen=report.rows_seen,rows_accepted=len(report.rows),rows_skipped=len(report.row_errors),duplicate_observations=report.duplicate_input_rows,new_observations=0,corrected_revisions=0,warnings_count=report.warnings_count,row_errors_total=len(report.row_errors))
            raise OzonProductsImportFailure(error=ImportPersistenceError(),result=_result(summary)) from error
    except OzonProductsImportFailure: raise
    except (UploadTooLarge,UnsupportedUploadMediaType) as error:
        if staged: staged.unlink(missing_ok=True)
        raise OzonProductsImportFailure(error=error,result=None)
    finally: IMPORT_LOCK.release()

def recover_interrupted_ozon_products_imports(*, db_path: Path | None = None, data_dir: Path = DATA_DIR) -> None:
    with transaction(db_path) as conn:
        lineage=LineageRepository(conn); lineage.fail_running_ozon_products_imports(finished_at=datetime.now(timezone.utc)); referenced=lineage.list_referenced_archive_paths()
    imports=data_dir/"imports"
    if not imports.exists(): return
    for path in imports.iterdir():
        if path.is_file() and (path.name.startswith(".upload-") and path.suffix==".part" or ARCHIVE_RE.fullmatch(path.name) and f"imports/{path.name}" not in referenced): path.unlink()
