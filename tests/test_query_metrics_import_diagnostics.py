import json
from datetime import datetime, timezone

import pytest

from backend.application.query_metrics_import_diagnostics import (
    QueryMetricsImportDiagnostics,
)


class FakeClock:
    def __init__(self):
        self.value = 1_000_000_000

    def __call__(self):
        return self.value

    def advance_ms(self, milliseconds):
        self.value += int(milliseconds * 1_000_000)


def test_monotonic_stage_and_elapsed_timings_are_deterministic(tmp_path):
    clock = FakeClock()
    diagnostic = QueryMetricsImportDiagnostics(
        data_dir=tmp_path,
        monotonic_ns=clock,
        utc_now=lambda: datetime(2026, 8, 29, tzinfo=timezone.utc),
    )

    stage_started = diagnostic.start_stage("stage_upload")
    clock.advance_ms(12.345)
    diagnostic.finish_stage("stage_upload", stage_started)
    diagnostic.initialize(
        batch_id=7,
        original_name="metrics.xlsx",
        content_sha256="a" * 64,
        byte_size=42,
    )
    clock.advance_ms(7.655)
    diagnostic.checkpoint()

    payload = json.loads(
        (tmp_path / "diagnostics/query_metrics/latest.json").read_text("utf-8")
    )
    assert payload["stages_ms"]["stage_upload"] == pytest.approx(12.345)
    assert payload["elapsed_ms"] == pytest.approx(20.0)


def test_checkpoint_atomically_writes_latest_and_per_batch_without_temp_files(tmp_path):
    diagnostic = QueryMetricsImportDiagnostics(data_dir=tmp_path)
    diagnostic.initialize(
        batch_id=11,
        original_name="metrics.xlsx",
        content_sha256="b" * 64,
        byte_size=123,
    )

    diagnostic.checkpoint()

    directory = tmp_path / "diagnostics/query_metrics"
    latest = json.loads((directory / "latest.json").read_text("utf-8"))
    per_batch = json.loads((directory / "import-11.json").read_text("utf-8"))
    assert latest == per_batch
    assert latest["schema_version"] == 1
    assert latest["state"] == "RUNNING"
    assert not [path for path in directory.iterdir() if path.suffix == ".tmp"]


def test_checkpoint_is_best_effort_when_atomic_write_fails(monkeypatch, tmp_path):
    diagnostic = QueryMetricsImportDiagnostics(data_dir=tmp_path)
    diagnostic.initialize(
        batch_id=12,
        original_name="metrics.xlsx",
        content_sha256="c" * 64,
        byte_size=5,
    )

    def fail_write(*args, **kwargs):
        raise OSError("diagnostic disk unavailable")

    monkeypatch.setattr(diagnostic, "_atomic_write", fail_write)
    diagnostic.checkpoint()
