import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from backend.config import VERSION


_STAGES = (
    "stage_upload",
    "lineage_create",
    "compat_copy",
    "parse",
    "archive_publish",
    "persistence_transaction_total",
)


class QueryMetricsImportDiagnostics:
    """Best-effort, file-only timing trace for one Query Metrics import."""

    def __init__(
        self,
        *,
        data_dir: Path,
        monotonic_ns: Callable[[], int] = time.perf_counter_ns,
        utc_now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self._directory = data_dir / "diagnostics" / "query_metrics"
        self._monotonic_ns = monotonic_ns
        self._utc_now = utc_now
        self._started_ns = monotonic_ns()
        self._batch_id: int | None = None
        started_at = self._wall_time()
        self.payload = {
            "schema_version": 1,
            "import_kind": "ozon_query_metrics_xlsx",
            "batch_id": None,
            "source": None,
            "runtime": {"pid": os.getpid(), "app_version": VERSION},
            "state": "RUNNING",
            "current_stage": "stage_upload",
            "started_at": started_at,
            "updated_at": started_at,
            "finished_at": None,
            "elapsed_ms": 0.0,
            "stages_ms": {stage: 0.0 for stage in _STAGES},
            "parse": {
                "rows_seen": 0,
                "rows_accepted": 0,
                "rows_skipped": 0,
                "duplicate_input_rows": 0,
            },
            "persistence": {
                "rows_total": 0,
                "rows_processed": 0,
                "resolve_search_query_ms": 0.0,
                "resolve_revision_ms": 0.0,
                "finish_lineage_ms": 0.0,
                "other_transaction_ms": None,
                "new_observations": 0,
                "duplicate_observations": 0,
                "corrected_revisions": 0,
            },
            "result": None,
        }

    def _wall_time(self) -> str:
        return self._utc_now().astimezone(timezone.utc).isoformat()

    def elapsed_ms(self, started_ns: int | None = None) -> float:
        start = self._started_ns if started_ns is None else started_ns
        return (self._monotonic_ns() - start) / 1_000_000

    def now_ns(self) -> int:
        return self._monotonic_ns()

    def start_stage(self, stage: str) -> int:
        self.payload["current_stage"] = stage
        return self._monotonic_ns()

    def finish_stage(self, stage: str, started_ns: int) -> None:
        self.payload["stages_ms"][stage] = self.elapsed_ms(started_ns)

    def initialize(
        self,
        *,
        batch_id: int,
        original_name: str,
        content_sha256: str,
        byte_size: int,
    ) -> None:
        self._batch_id = batch_id
        self.payload["batch_id"] = batch_id
        self.payload["source"] = {
            "original_name": original_name,
            "content_sha256": content_sha256,
            "byte_size": byte_size,
        }
        self.checkpoint()

    def record_parse(self, report) -> None:
        self.payload["parse"].update(
            rows_seen=report.rows_seen,
            rows_accepted=len(report.rows),
            rows_skipped=len(report.row_errors),
            duplicate_input_rows=report.duplicate_input_rows,
        )
        self.payload["persistence"].update(
            rows_total=len(report.rows),
            duplicate_observations=report.duplicate_input_rows,
        )

    def add_persistence_timing(self, field: str, milliseconds: float) -> None:
        self.payload["persistence"][field] += milliseconds

    def record_progress(self, *, rows_processed: int, new: int, duplicate: int,
                        corrected: int) -> None:
        self.payload["persistence"].update(
            rows_processed=rows_processed,
            new_observations=new,
            duplicate_observations=duplicate,
            corrected_revisions=corrected,
        )

    def finish_transaction(self, started_ns: int) -> None:
        total = self.elapsed_ms(started_ns)
        self.payload["stages_ms"]["persistence_transaction_total"] = total
        persistence = self.payload["persistence"]
        measured = (
            persistence["resolve_search_query_ms"]
            + persistence["resolve_revision_ms"]
            + persistence["finish_lineage_ms"]
        )
        persistence["other_transaction_ms"] = max(0.0, total - measured)

    def finish(self, *, state: str, result=None) -> None:
        self.payload["state"] = state
        if state == "SUCCESS":
            self.payload["current_stage"] = "complete"
        self.payload["finished_at"] = self._wall_time()
        if result is not None:
            self.payload["result"] = {
                "status": result.status.value,
                "rows_seen": result.rows_seen,
                "rows_accepted": result.rows_accepted,
                "rows_skipped": result.rows_skipped,
                "duplicate_observations": result.duplicate_observations,
                "new_observations": result.new_observations,
                "corrected_revisions": result.corrected_revisions,
                "warnings_count": result.warnings_count,
                "row_errors_total": result.row_errors_total,
            }
        self.checkpoint()

    def checkpoint(self) -> None:
        if self._batch_id is None:
            return
        self.payload["updated_at"] = self._wall_time()
        self.payload["elapsed_ms"] = self.elapsed_ms()
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
            encoded = json.dumps(
                self.payload, ensure_ascii=False, indent=2, sort_keys=True
            ) + "\n"
            self._atomic_write(
                self._directory / f"import-{self._batch_id}.json", encoded
            )
            self._atomic_write(self._directory / "latest.json", encoded)
        except OSError:
            pass

    def _atomic_write(self, path: Path, content: str) -> None:
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
                stream.flush()
            os.replace(temporary, path)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
