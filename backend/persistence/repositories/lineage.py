import sqlite3
from datetime import date, datetime
from pathlib import PurePosixPath, PureWindowsPath

from backend.domain.lineage import (
    ImportBatch, ImportHistoryItem,
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
from backend.domain.product_query import OzonSellerQueriesImportSummary
from backend.domain.query_metric import OzonQueryMetricsImportSummary
from backend.domain.search_visibility import OzonSearchVisibilityImportSummary


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

    def finish_ozon_search_visibility_import(self, batch_id: int, *, status: ImportStatus, observed_at: datetime | None, query_text: str | None, cluster_name: str | None, declared_rows: int | None, rows_seen: int, rows_accepted: int, rows_skipped: int, duplicate_observations: int, new_observations: int, corrected_revisions: int, warnings_count: int, row_errors_total: int) -> OzonSearchVisibilityImportSummary:
        batch = self.get_import_batch(batch_id)
        if batch is None:
            raise ImportBatchNotFound(batch_id)
        if batch.import_kind != "ozon_search_visibility_xlsx" or batch.status is not ImportStatus.RUNNING or status is ImportStatus.RUNNING:
            raise InvalidImportStatusTransition(
                f"cannot transition {batch.status.value} to {status.value}"
            )
        counts = (rows_seen, rows_accepted, rows_skipped, duplicate_observations, new_observations, corrected_revisions, warnings_count, row_errors_total)
        if any(value < 0 for value in counts):
            raise ValueError("counts must be non-negative")
        if declared_rows is not None and declared_rows <= 0:
            raise ValueError("declared rows must be positive")
        cursor = self._conn.execute(
            """UPDATE import_batches SET status=?,finished_at=?,observed_at=?,search_query_text=?,cluster_name=?,declared_rows=?,rows_seen=?,rows_accepted=?,rows_skipped=?,duplicate_observations=?,new_observations=?,corrected_revisions=?,warnings_count=?,row_errors_total=?
               WHERE id=? AND import_kind='ozon_search_visibility_xlsx' AND status=?""",
            (status.value, datetime_to_db(utc_now()), None if observed_at is None else datetime_to_db(observed_at), query_text, cluster_name, declared_rows, *counts, batch_id, ImportStatus.RUNNING.value),
        )
        if cursor.rowcount != 1:
            raise InvalidImportStatusTransition("import batch was already finished")
        result = self._get_search_visibility_summary(batch_id)
        if result is None:
            raise ImportBatchNotFound(batch_id)
        return result

    def finish_ozon_seller_queries_import(self, batch_id: int, *, status: ImportStatus,
            generated_at: datetime | None, period_start: date | None,
            period_end: date | None, product_ozon_id: str | None, rows_seen: int,
            rows_accepted: int, rows_skipped: int, duplicate_observations: int,
            new_observations: int, corrected_revisions: int, warnings_count: int,
            row_errors_total: int) -> OzonSellerQueriesImportSummary:
        self._validate_pr5_finish(
            batch_id, expected_kind="ozon_seller_queries_xlsx", status=status,
            period_start=period_start, period_end=period_end,
            counts=(rows_seen, rows_accepted, rows_skipped, duplicate_observations,
                    new_observations, corrected_revisions, warnings_count, row_errors_total),
        )
        if generated_at is not None:
            datetime_to_db(generated_at)
        if product_ozon_id is not None and (
            not product_ozon_id.isascii() or not product_ozon_id.isdigit()
            or int(product_ozon_id) <= 0
        ):
            raise ValueError("product Ozon ID must contain positive ASCII digits")
        cursor = self._conn.execute(
            """UPDATE import_batches SET status=?,finished_at=?,report_generated_at=?,
               period_start=?,period_end=?,report_product_ozon_id=?,rows_seen=?,
               rows_accepted=?,rows_skipped=?,duplicate_observations=?,new_observations=?,
               corrected_revisions=?,warnings_count=?,row_errors_total=?
               WHERE id=? AND import_kind='ozon_seller_queries_xlsx' AND status=?""",
            (status.value, datetime_to_db(utc_now()),
             None if generated_at is None else datetime_to_db(generated_at),
             None if period_start is None else period_start.isoformat(),
             None if period_end is None else period_end.isoformat(), product_ozon_id,
             rows_seen, rows_accepted, rows_skipped, duplicate_observations,
             new_observations, corrected_revisions, warnings_count, row_errors_total,
             batch_id, ImportStatus.RUNNING.value),
        )
        if cursor.rowcount != 1:
            raise InvalidImportStatusTransition("import batch was already finished")
        row = self._conn.execute(self._SUMMARY_SELECT + " WHERE b.id=?", (batch_id,)).fetchone()
        return self._seller_queries_summary(row)

    def finish_ozon_query_metrics_import(self, batch_id: int, *, status: ImportStatus,
            period_start: date | None, period_end: date | None, sort_context: str | None,
            rows_seen: int, rows_accepted: int, rows_skipped: int,
            duplicate_observations: int, new_observations: int,
            corrected_revisions: int, warnings_count: int,
            row_errors_total: int) -> OzonQueryMetricsImportSummary:
        self._validate_pr5_finish(
            batch_id, expected_kind="ozon_query_metrics_xlsx", status=status,
            period_start=period_start, period_end=period_end,
            counts=(rows_seen, rows_accepted, rows_skipped, duplicate_observations,
                    new_observations, corrected_revisions, warnings_count, row_errors_total),
        )
        supported_sort = "Сортировка: По убыванию в Популярность запроса"
        if sort_context is not None and sort_context != supported_sort:
            raise ValueError("unsupported sort context")
        cursor = self._conn.execute(
            """UPDATE import_batches SET status=?,finished_at=?,period_start=?,period_end=?,
               sort_context=?,rows_seen=?,rows_accepted=?,rows_skipped=?,
               duplicate_observations=?,new_observations=?,corrected_revisions=?,
               warnings_count=?,row_errors_total=?
               WHERE id=? AND import_kind='ozon_query_metrics_xlsx' AND status=?""",
            (status.value, datetime_to_db(utc_now()),
             None if period_start is None else period_start.isoformat(),
             None if period_end is None else period_end.isoformat(), sort_context,
             rows_seen, rows_accepted, rows_skipped, duplicate_observations,
             new_observations, corrected_revisions, warnings_count, row_errors_total,
             batch_id, ImportStatus.RUNNING.value),
        )
        if cursor.rowcount != 1:
            raise InvalidImportStatusTransition("import batch was already finished")
        row = self._conn.execute(self._SUMMARY_SELECT + " WHERE b.id=?", (batch_id,)).fetchone()
        return self._query_metrics_summary(row)

    def _get_summary(self, batch_id: int) -> OzonProductsImportSummary | None:
        row = self._conn.execute("SELECT b.*,a.id artifact_id,a.artifact_kind,a.original_name,a.content_sha256,a.byte_size,a.stored_relpath,a.created_at artifact_created_at FROM import_batches b LEFT JOIN source_artifacts a ON a.import_batch_id=b.id WHERE b.id=?", (batch_id,)).fetchone()
        return None if row is None else self._summary(row)

    def list_ozon_products_imports(self, *, limit: int, offset: int) -> list[OzonProductsImportSummary]:
        if not 1 <= limit <= 100 or offset < 0: raise ValueError("invalid pagination")
        rows = self._conn.execute("SELECT b.*,a.id artifact_id,a.artifact_kind,a.original_name,a.content_sha256,a.byte_size,a.stored_relpath,a.created_at artifact_created_at FROM import_batches b LEFT JOIN source_artifacts a ON a.import_batch_id=b.id WHERE b.import_kind='ozon_products_xlsx' ORDER BY b.started_at DESC,b.id DESC LIMIT ? OFFSET ?", (limit,offset)).fetchall()
        return [self._summary(row) for row in rows]

    def count_ozon_products_imports(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM import_batches WHERE import_kind='ozon_products_xlsx'").fetchone()[0]

    def list_ozon_search_visibility_imports(self, *, limit: int, offset: int) -> list[OzonSearchVisibilityImportSummary]:
        self._validate_pagination(limit=limit, offset=offset)
        rows = self._conn.execute(
            self._SUMMARY_SELECT + " WHERE b.import_kind='ozon_search_visibility_xlsx' ORDER BY b.started_at DESC,b.id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [self._search_visibility_summary(row) for row in rows]

    def count_ozon_search_visibility_imports(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM import_batches WHERE import_kind='ozon_search_visibility_xlsx'").fetchone()[0]

    def list_referenced_archive_paths(self) -> set[str]:
        return {row[0] for row in self._conn.execute("SELECT stored_relpath FROM source_artifacts WHERE stored_relpath IS NOT NULL AND stored_relpath LIKE 'imports/%'")}

    def list_import_history(self, *, limit: int, offset: int) -> list[ImportHistoryItem]:
        self._validate_pagination(limit=limit, offset=offset)
        rows = self._conn.execute(
            self._SUMMARY_SELECT + " WHERE b.import_kind IN (?, ?, ?, ?) ORDER BY b.started_at DESC,b.id DESC LIMIT ? OFFSET ?",
            ("ozon_products_xlsx", "ozon_search_visibility_xlsx",
             "ozon_seller_queries_xlsx", "ozon_query_metrics_xlsx", limit, offset),
        ).fetchall()
        return [self._history_item(row) for row in rows]

    def count_import_history(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM import_batches WHERE import_kind IN (?, ?, ?, ?)", ("ozon_products_xlsx", "ozon_search_visibility_xlsx", "ozon_seller_queries_xlsx", "ozon_query_metrics_xlsx")).fetchone()[0]

    def get_pr5_source_availability(self) -> dict[str, bool]:
        successful = (ImportStatus.SUCCESS.value, ImportStatus.PARTIAL_SUCCESS.value)
        row = self._conn.execute(
            """SELECT
               EXISTS(SELECT 1 FROM import_batches WHERE import_kind=? AND status IN (?,?)),
               EXISTS(SELECT 1 FROM import_batches WHERE import_kind=? AND status IN (?,?))""",
            ("ozon_seller_queries_xlsx", *successful,
             "ozon_query_metrics_xlsx", *successful),
        ).fetchone()
        return {"own_product_queries": bool(row[0]), "query_metrics": bool(row[1])}

    def fail_running_ozon_products_imports(self, *, finished_at: datetime) -> int:
        cursor = self._conn.execute("UPDATE import_batches SET status=?,finished_at=? WHERE import_kind='ozon_products_xlsx' AND status=?", (ImportStatus.FAILED.value,datetime_to_db(finished_at),ImportStatus.RUNNING.value))
        return cursor.rowcount

    def fail_running_ozon_search_visibility_imports(self, *, finished_at: datetime) -> int:
        cursor = self._conn.execute("UPDATE import_batches SET status=?,finished_at=? WHERE import_kind='ozon_search_visibility_xlsx' AND status=?", (ImportStatus.FAILED.value,datetime_to_db(finished_at),ImportStatus.RUNNING.value))
        return cursor.rowcount

    def fail_running_ozon_seller_queries_imports(self, *, finished_at: datetime) -> int:
        return self._fail_running("ozon_seller_queries_xlsx", finished_at=finished_at)

    def fail_running_ozon_query_metrics_imports(self, *, finished_at: datetime) -> int:
        return self._fail_running("ozon_query_metrics_xlsx", finished_at=finished_at)

    def _fail_running(self, import_kind: str, *, finished_at: datetime) -> int:
        cursor = self._conn.execute(
            "UPDATE import_batches SET status=?,finished_at=? WHERE import_kind=? AND status=?",
            (ImportStatus.FAILED.value, datetime_to_db(finished_at), import_kind,
             ImportStatus.RUNNING.value),
        )
        return cursor.rowcount

    _SUMMARY_SELECT = "SELECT b.*,a.id artifact_id,a.artifact_kind,a.original_name,a.content_sha256,a.byte_size,a.stored_relpath,a.created_at artifact_created_at FROM import_batches b LEFT JOIN source_artifacts a ON a.import_batch_id=b.id"

    def _get_search_visibility_summary(self, batch_id: int) -> OzonSearchVisibilityImportSummary | None:
        row = self._conn.execute(self._SUMMARY_SELECT + " WHERE b.id=?", (batch_id,)).fetchone()
        return None if row is None else self._search_visibility_summary(row)

    @staticmethod
    def _artifact(row: sqlite3.Row) -> SourceArtifact | None:
        return None if row["artifact_id"] is None else SourceArtifact(row["artifact_id"],row["id"],row["artifact_kind"],row["original_name"],row["content_sha256"],row["byte_size"],row["stored_relpath"],datetime_from_db(row["artifact_created_at"]))

    @classmethod
    def _search_visibility_summary(cls, row: sqlite3.Row) -> OzonSearchVisibilityImportSummary:
        return OzonSearchVisibilityImportSummary(
            row["id"], row["source"], row["import_kind"], ImportStatus(row["status"]),
            None if row["observed_at"] is None else datetime_from_db(row["observed_at"]),
            row["search_query_text"], row["cluster_name"], row["declared_rows"],
            *(0 if row[name] is None else row[name] for name in ("rows_seen","rows_accepted","rows_skipped","duplicate_observations","new_observations","corrected_revisions","warnings_count","row_errors_total")),
            datetime_from_db(row["started_at"]), None if row["finished_at"] is None else datetime_from_db(row["finished_at"]), cls._artifact(row),
        )

    @classmethod
    def _history_item(cls, row: sqlite3.Row) -> ImportHistoryItem:
        kind = row["import_kind"]
        products = kind == "ozon_products_xlsx"
        visibility = kind == "ozon_search_visibility_xlsx"
        seller = kind == "ozon_seller_queries_xlsx"
        report_types = {
            "ozon_products_xlsx": "OZON_PRODUCTS",
            "ozon_search_visibility_xlsx": "OZON_SEARCH_VISIBILITY",
            "ozon_seller_queries_xlsx": "OZON_OWN_PRODUCT_QUERIES",
            "ozon_query_metrics_xlsx": "OZON_QUERY_METRICS",
        }
        return ImportHistoryItem(
            import_batch_id=row["id"], source=row["source"], import_kind=kind,
            report_type=report_types[kind], status=ImportStatus(row["status"]),
            report_generated_on=date.fromisoformat(row["report_generated_on"])
                if products and row["report_generated_on"] is not None else None,
            report_window_days=row["report_window_days"] if products else None,
            observed_at=datetime_from_db(row["observed_at"])
                if visibility and row["observed_at"] is not None else None,
            query_text=row["search_query_text"] if visibility else None,
            cluster_name=row["cluster_name"] if visibility else None,
            declared_rows=row["declared_rows"] if visibility else None,
            period_start=date.fromisoformat(row["period_start"])
                if kind in ("ozon_seller_queries_xlsx", "ozon_query_metrics_xlsx") and row["period_start"] else None,
            period_end=date.fromisoformat(row["period_end"])
                if kind in ("ozon_seller_queries_xlsx", "ozon_query_metrics_xlsx") and row["period_end"] else None,
            report_generated_at=datetime_from_db(row["report_generated_at"])
                if seller and row["report_generated_at"] else None,
            report_product_ozon_id=row["report_product_ozon_id"] if seller else None,
            sort_context=row["sort_context"] if kind == "ozon_query_metrics_xlsx" else None,
            **{name: 0 if row[name] is None else row[name] for name in
               ("rows_seen", "rows_accepted", "rows_skipped", "duplicate_observations",
                "new_observations", "corrected_revisions", "warnings_count", "row_errors_total")},
            started_at=datetime_from_db(row["started_at"]),
            finished_at=None if row["finished_at"] is None else datetime_from_db(row["finished_at"]),
            source_artifact=cls._artifact(row),
        )

    def _validate_pr5_finish(self, batch_id: int, *, expected_kind: str,
            status: ImportStatus, period_start: date | None, period_end: date | None,
            counts: tuple[int, ...]) -> None:
        batch = self.get_import_batch(batch_id)
        if batch is None:
            raise ImportBatchNotFound(batch_id)
        if batch.import_kind != expected_kind or batch.status is not ImportStatus.RUNNING or status is ImportStatus.RUNNING:
            raise InvalidImportStatusTransition(
                f"cannot transition {batch.status.value} to {status.value}"
            )
        if any(value < 0 for value in counts):
            raise ValueError("counts must be non-negative")
        if (period_start is None) != (period_end is None):
            raise ValueError("period bounds must both be present or absent")
        if period_start is not None and period_start > period_end:
            raise ValueError("period start must not follow period end")

    @classmethod
    def _seller_queries_summary(cls, row: sqlite3.Row) -> OzonSellerQueriesImportSummary:
        return OzonSellerQueriesImportSummary(
            row["id"], row["source"], row["import_kind"], ImportStatus(row["status"]),
            None if row["report_generated_at"] is None else datetime_from_db(row["report_generated_at"]),
            None if row["period_start"] is None else date.fromisoformat(row["period_start"]),
            None if row["period_end"] is None else date.fromisoformat(row["period_end"]),
            row["report_product_ozon_id"],
            *(0 if row[name] is None else row[name] for name in ("rows_seen", "rows_accepted", "rows_skipped", "duplicate_observations", "new_observations", "corrected_revisions", "warnings_count", "row_errors_total")),
            datetime_from_db(row["started_at"]), None if row["finished_at"] is None else datetime_from_db(row["finished_at"]), cls._artifact(row),
        )

    @classmethod
    def _query_metrics_summary(cls, row: sqlite3.Row) -> OzonQueryMetricsImportSummary:
        return OzonQueryMetricsImportSummary(
            row["id"], row["source"], row["import_kind"], ImportStatus(row["status"]),
            None if row["period_start"] is None else date.fromisoformat(row["period_start"]),
            None if row["period_end"] is None else date.fromisoformat(row["period_end"]),
            row["sort_context"],
            *(0 if row[name] is None else row[name] for name in ("rows_seen", "rows_accepted", "rows_skipped", "duplicate_observations", "new_observations", "corrected_revisions", "warnings_count", "row_errors_total")),
            datetime_from_db(row["started_at"]), None if row["finished_at"] is None else datetime_from_db(row["finished_at"]), cls._artifact(row),
        )

    @staticmethod
    def _validate_pagination(*, limit: int, offset: int) -> None:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("invalid pagination")

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
