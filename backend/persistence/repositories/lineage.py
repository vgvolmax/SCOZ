import sqlite3
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
