import sqlite3
from datetime import date, datetime
from pathlib import PurePosixPath, PureWindowsPath

from backend.domain.lineage import (
    ImportBatch,
    ImportBatchNotFound,
    ImportStatus,
    InvalidImportStatusTransition,
    InvalidSourceArtifactMetadata,
    InvalidStoredRelativePath,
    SourceArtifact,
    datetime_from_db,
    datetime_to_db,
    utc_now,
)
from backend.domain.product_snapshot import OzonProductsImportSummary


class LineageRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create_import_batch(self, *, source: str, import_kind: str) -> ImportBatch:
        started_at = datetime_to_db(utc_now())
        cursor = self._conn.execute(
            "INSERT INTO import_batches (source, import_kind, status, started_at) VALUES (?, ?, ?, ?)",
            (source, import_kind, ImportStatus.RUNNING.value, started_at),
        )
        return self.get_import_batch(cursor.lastrowid)  # type: ignore[return-value]

    def get_import_batch(self, batch_id: int) -> ImportBatch | None:
        row = self._conn.execute(
            "SELECT id, source, import_kind, status, started_at, finished_at FROM import_batches WHERE id = ?",
            (batch_id,),
        ).fetchone()
        return None if row is None else self._batch_from_row(row)

    def finish_import_batch(self, batch_id: int, *, status: ImportStatus) -> ImportBatch:
        batch = self.get_import_batch(batch_id)
        if batch is None:
            raise ImportBatchNotFound(batch_id)
        if batch.status is not ImportStatus.RUNNING or status is ImportStatus.RUNNING:
            raise InvalidImportStatusTransition(f"cannot transition {batch.status.value} to {status.value}")
        self._conn.execute(
            "UPDATE import_batches SET status = ?, finished_at = ? WHERE id = ?",
            (status.value, datetime_to_db(utc_now()), batch_id),
        )
        return self.get_import_batch(batch_id)  # type: ignore[return-value]

    def add_source_artifact(
        self, batch_id: int, *, artifact_kind: str, original_name: str | None,
        content_sha256: str, byte_size: int, stored_relpath: str | None = None,
    ) -> SourceArtifact:
        if byte_size < 0 or len(content_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in content_sha256
        ):
            raise InvalidSourceArtifactMetadata("invalid source artifact metadata")
        if stored_relpath is not None and not self._valid_stored_relpath(stored_relpath):
            raise InvalidStoredRelativePath(stored_relpath)
        if self.get_import_batch(batch_id) is None:
            raise ImportBatchNotFound(batch_id)
        try:
            cursor = self._conn.execute(
                "INSERT INTO source_artifacts (import_batch_id, artifact_kind, original_name, content_sha256, byte_size, stored_relpath, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (batch_id, artifact_kind, original_name, content_sha256, byte_size,
                 stored_relpath, datetime_to_db(utc_now())),
            )
        except sqlite3.IntegrityError as error:
            if error.sqlite_errorname == "SQLITE_CONSTRAINT_FOREIGNKEY":
                raise ImportBatchNotFound(batch_id) from error
            raise
        return self.get_source_artifact(cursor.lastrowid)  # type: ignore[return-value]

    def get_source_artifact(self, artifact_id: int) -> SourceArtifact | None:
        row = self._conn.execute(
            "SELECT id, import_batch_id, artifact_kind, original_name, content_sha256, byte_size, stored_relpath, created_at FROM source_artifacts WHERE id = ?",
            (artifact_id,),
        ).fetchone()
        return None if row is None else SourceArtifact(
            id=row["id"], import_batch_id=row["import_batch_id"],
            artifact_kind=row["artifact_kind"], original_name=row["original_name"],
            content_sha256=row["content_sha256"], byte_size=row["byte_size"],
            stored_relpath=row["stored_relpath"], created_at=datetime_from_db(row["created_at"]),
        )

    def set_source_artifact_stored_relpath(self, artifact_id: int, stored_relpath: str) -> SourceArtifact:
        if not self._valid_stored_relpath(stored_relpath): raise InvalidStoredRelativePath(stored_relpath)
        self._conn.execute("UPDATE source_artifacts SET stored_relpath=? WHERE id=?", (stored_relpath, artifact_id))
        result = self.get_source_artifact(artifact_id)
        if result is None: raise LookupError(artifact_id)
        return result

    def finish_ozon_products_import(self, batch_id: int, *, status: ImportStatus, report_generated_on: date | None, report_window_days: int | None, rows_seen: int, rows_accepted: int, rows_skipped: int, duplicate_observations: int, new_observations: int, corrected_revisions: int, warnings_count: int, row_errors_total: int) -> OzonProductsImportSummary:
        batch = self.get_import_batch(batch_id)
        if batch is None:
            raise ImportBatchNotFound(batch_id)
        if batch.status is not ImportStatus.RUNNING or status is ImportStatus.RUNNING:
            raise InvalidImportStatusTransition(
                f"cannot transition {batch.status.value} to {status.value}"
            )
        counts = (rows_seen, rows_accepted, rows_skipped, duplicate_observations, new_observations, corrected_revisions, warnings_count, row_errors_total)
        if any(value < 0 for value in counts): raise ValueError("counts must be non-negative")
        cursor = self._conn.execute("UPDATE import_batches SET status=?,finished_at=?,report_generated_on=?,report_window_days=?,rows_seen=?,rows_accepted=?,rows_skipped=?,duplicate_observations=?,new_observations=?,corrected_revisions=?,warnings_count=?,row_errors_total=? WHERE id=? AND status=?", (status.value, datetime_to_db(utc_now()), None if report_generated_on is None else report_generated_on.isoformat(), report_window_days, *counts, batch_id, ImportStatus.RUNNING.value))
        if cursor.rowcount != 1:
            raise InvalidImportStatusTransition("import batch was already finished")
        result = self._get_summary(batch_id)
        if result is None: raise ImportBatchNotFound(batch_id)
        return result

    def _get_summary(self, batch_id: int) -> OzonProductsImportSummary | None:
        row = self._conn.execute("SELECT b.*,a.id artifact_id,a.artifact_kind,a.original_name,a.content_sha256,a.byte_size,a.stored_relpath,a.created_at artifact_created_at FROM import_batches b LEFT JOIN source_artifacts a ON a.import_batch_id=b.id WHERE b.id=?", (batch_id,)).fetchone()
        return None if row is None else self._summary(row)

    def list_ozon_products_imports(self, *, limit: int, offset: int) -> list[OzonProductsImportSummary]:
        if not 1 <= limit <= 100 or offset < 0: raise ValueError("invalid pagination")
        rows = self._conn.execute("SELECT b.*,a.id artifact_id,a.artifact_kind,a.original_name,a.content_sha256,a.byte_size,a.stored_relpath,a.created_at artifact_created_at FROM import_batches b LEFT JOIN source_artifacts a ON a.import_batch_id=b.id WHERE b.import_kind='ozon_products_xlsx' ORDER BY b.started_at DESC,b.id DESC LIMIT ? OFFSET ?", (limit,offset)).fetchall()
        return [self._summary(row) for row in rows]

    def count_ozon_products_imports(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM import_batches WHERE import_kind='ozon_products_xlsx'").fetchone()[0]

    def list_referenced_pr3_archive_paths(self) -> set[str]:
        return {row[0] for row in self._conn.execute("SELECT a.stored_relpath FROM source_artifacts a JOIN import_batches b ON b.id=a.import_batch_id WHERE b.import_kind='ozon_products_xlsx' AND a.stored_relpath IS NOT NULL")}

    def fail_running_ozon_products_imports(self, *, finished_at: datetime) -> int:
        cursor = self._conn.execute("UPDATE import_batches SET status=?,finished_at=? WHERE import_kind='ozon_products_xlsx' AND status=?", (ImportStatus.FAILED.value,datetime_to_db(finished_at),ImportStatus.RUNNING.value))
        return cursor.rowcount

    @staticmethod
    def _summary(row: sqlite3.Row) -> OzonProductsImportSummary:
        artifact = None if row["artifact_id"] is None else SourceArtifact(row["artifact_id"],row["id"],row["artifact_kind"],row["original_name"],row["content_sha256"],row["byte_size"],row["stored_relpath"],datetime_from_db(row["artifact_created_at"]))
        return OzonProductsImportSummary(row["id"],row["source"],row["import_kind"],ImportStatus(row["status"]),None if row["report_generated_on"] is None else date.fromisoformat(row["report_generated_on"]),row["report_window_days"],*(0 if row[name] is None else row[name] for name in ("rows_seen","rows_accepted","rows_skipped","duplicate_observations","new_observations","corrected_revisions","warnings_count","row_errors_total")),datetime_from_db(row["started_at"]),None if row["finished_at"] is None else datetime_from_db(row["finished_at"]),artifact)

    @staticmethod
    def _batch_from_row(row: sqlite3.Row) -> ImportBatch:
        return ImportBatch(
            id=row["id"], source=row["source"], import_kind=row["import_kind"],
            status=ImportStatus(row["status"]), started_at=datetime_from_db(row["started_at"]),
            finished_at=None if row["finished_at"] is None else datetime_from_db(row["finished_at"]),
        )

    @staticmethod
    def _valid_stored_relpath(value: str) -> bool:
        if not value or "\\" in value:
            return False
        windows_path = PureWindowsPath(value)
        path = PurePosixPath(value)
        return (
            not windows_path.drive
            and not windows_path.is_absolute()
            and not path.is_absolute()
            and ".." not in path.parts
            and value == path.as_posix()
        )
