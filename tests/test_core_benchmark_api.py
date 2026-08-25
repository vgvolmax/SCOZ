from dataclasses import replace
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

import backend.main as main
from backend.domain.core_benchmark import (
    BenchmarkConfidence, BenchmarkRevisionContext, BenchmarkSampleValue,
    ComparisonPosition, CoreBenchmarkMetric, CoreBenchmarkMetricId,
    CoreBenchmarkReadiness, CoreBenchmarkResult, MetricDirection,
    MetricExclusionReason, MetricReadiness, MetricUnit,
    ObservationContext, CORE_BENCHMARK_METRIC_ORDER,
)
from backend.domain.product import ProductNotFound
from backend.domain.benchmark_selection import ProductNotOwnedError


class _Service:
    result = None
    error = None
    def __init__(self, **_kwargs): pass
    def get_core_benchmark(self, _product_id):
        if self.error: raise self.error
        return self.result


def _metric():
    return CoreBenchmarkMetric(
        CoreBenchmarkMetricId.ORDERED_AMOUNT_RUB, "Заказано на сумму", MetricUnit.RUB,
        MetricDirection.HIGHER_IS_BETTER, False, MetricReadiness.READY,
        Decimal("1.2300"), Decimal("1.20"), None, None, Decimal("0.0300"), 3,
        (BenchmarkSampleValue(2, "20", None, Decimal("1.200")),) * 3,
        ComparisonPosition.ABOVE_MEDIAN, BenchmarkConfidence.LOW,
        {reason: 0 for reason in MetricExclusionReason},
    )


def test_core_benchmark_ready_response_serializes_canonical_decimal_strings(monkeypatch):
    _Service.error = None
    _Service.result = CoreBenchmarkResult(1, CoreBenchmarkReadiness.READY,
        BenchmarkRevisionContext(1, 2, 3, 3), None, (_metric(),))
    monkeypatch.setattr(main, "CoreBenchmarkService", _Service)
    response = TestClient(main.app).get("/api/products/1/core-benchmark")
    assert response.status_code == 200
    metric = response.json()["metrics"][0]
    assert metric["own_value"] == "1.23" and metric["absolute_delta"] == "0.03"
    assert [item["value"] for item in metric["sample_values"]] == ["1.2"] * 3
    assert set(response.json()) == {"product_id", "readiness", "benchmark", "observation", "metrics"}
    assert set(metric) == {"metric_id", "label", "unit", "direction", "is_estimate", "readiness",
                           "own_value", "median", "p25", "p75", "absolute_delta", "sample_size",
                           "sample_values", "comparison_position", "confidence", "exclusion_summary"}
    assert set(metric["sample_values"][0]) == {"product_id", "ozon_product_id", "title", "value"}
    assert set(metric["exclusion_summary"]) == {reason.value for reason in MetricExclusionReason}


def test_core_benchmark_returns_normal_readiness_over_200(monkeypatch):
    _Service.error = None
    _Service.result = CoreBenchmarkResult(1, CoreBenchmarkReadiness.NO_BENCHMARK, None, None, ())
    monkeypatch.setattr(main, "CoreBenchmarkService", _Service)
    response = TestClient(main.app).get("/api/products/1/core-benchmark")
    assert response.status_code == 200 and response.json()["readiness"] == "NO_BENCHMARK"


def test_core_benchmark_missing_product_uses_exact_404_envelope(monkeypatch):
    _Service.error = ProductNotFound(1)
    monkeypatch.setattr(main, "CoreBenchmarkService", _Service)
    response = TestClient(main.app).get("/api/products/1/core-benchmark")
    assert response.status_code == 404
    assert response.json() == {"error": {"code": "PRODUCT_NOT_FOUND", "message": "Товар не найден."}}
    _Service.error = None


def test_core_benchmark_invalid_id_uses_422():
    assert TestClient(main.app).get("/api/products/0/core-benchmark").status_code == 422


def test_core_benchmark_non_owned_uses_exact_409_envelope(monkeypatch):
    _Service.error = ProductNotOwnedError()
    monkeypatch.setattr(main, "CoreBenchmarkService", _Service)
    response = TestClient(main.app).get("/api/products/1/core-benchmark")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PRODUCT_NOT_OWNED"
    _Service.error = None


def test_core_benchmark_ready_response_has_exact_all_metric_shape_and_order(monkeypatch):
    _Service.error = None
    metrics = tuple(replace(_metric(), metric_id=metric_id) for metric_id in CORE_BENCHMARK_METRIC_ORDER)
    observation = ObservationContext(date(2026, 8, 23), 7, 101, 2,
                                     datetime(2026, 8, 24, 10, 15, tzinfo=timezone.utc))
    _Service.result = CoreBenchmarkResult(1, CoreBenchmarkReadiness.READY,
        BenchmarkRevisionContext(7, 12, 3, 3), observation, metrics)
    monkeypatch.setattr(main, "CoreBenchmarkService", _Service)
    payload = TestClient(main.app).get("/api/products/1/core-benchmark").json()
    assert [metric["metric_id"] for metric in payload["metrics"]] == [item.value for item in CORE_BENCHMARK_METRIC_ORDER]
    assert payload["benchmark"] == {"benchmark_set_id": 7, "benchmark_set_revision_id": 12,
                                     "benchmark_revision_number": 3, "benchmark_member_count": 3}
    assert payload["observation"] == {"report_generated_on": "2026-08-23", "report_window_days": 7,
        "snapshot_id": 101, "snapshot_revision": 2, "imported_at": "2026-08-24T10:15:00+00:00"}


@pytest.mark.parametrize("readiness", tuple(CoreBenchmarkReadiness))
def test_core_benchmark_returns_each_normal_readiness_over_200(monkeypatch, readiness):
    _Service.error = None
    _Service.result = CoreBenchmarkResult(1, readiness, None, None, ())
    monkeypatch.setattr(main, "CoreBenchmarkService", _Service)
    response = TestClient(main.app).get("/api/products/1/core-benchmark")
    assert response.status_code == 200 and response.json()["readiness"] == readiness.value


def test_core_benchmark_partial_metrics_keep_nulls_and_exclusion_shape(monkeypatch):
    _Service.error = None
    partial = replace(_metric(), readiness=MetricReadiness.OWN_VALUE_UNAVAILABLE,
                      own_value=None, absolute_delta=None,
                      comparison_position=ComparisonPosition.UNAVAILABLE,
                      exclusion_summary={
                          MetricExclusionReason.NO_COMPATIBLE_OBSERVATION: 1,
                          MetricExclusionReason.SOURCE_METRIC_UNAVAILABLE: 1,
                          MetricExclusionReason.DERIVED_VALUE_UNAVAILABLE: 0,
                      })
    _Service.result = CoreBenchmarkResult(1, CoreBenchmarkReadiness.READY,
        BenchmarkRevisionContext(1, 2, 3, 5), None, (partial,))
    monkeypatch.setattr(main, "CoreBenchmarkService", _Service)
    metric = TestClient(main.app).get("/api/products/1/core-benchmark").json()["metrics"][0]
    assert metric["own_value"] is None and metric["absolute_delta"] is None
    assert metric["comparison_position"] == "UNAVAILABLE"
    assert metric["exclusion_summary"] == {"NO_COMPATIBLE_OBSERVATION": 1,
        "SOURCE_METRIC_UNAVAILABLE": 1, "DERIVED_VALUE_UNAVAILABLE": 0}


def test_repeated_get_creates_no_rows(tmp_path, monkeypatch):
    from backend.persistence.connection import connect
    from backend.persistence.database import initialize_database
    from backend.persistence.repositories.products import ProductRepository
    path = tmp_path / "api.db"; initialize_database(path)
    connection = connect(path); product = ProductRepository(connection).create_product(is_owned=True); connection.commit()
    tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    before = {table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in tables}
    connection.close()
    monkeypatch.setattr(main, "resolve_db_path", lambda: path)
    monkeypatch.setattr(main, "CoreBenchmarkService", __import__("backend.application.core_benchmark", fromlist=["CoreBenchmarkService"]).CoreBenchmarkService)
    client = TestClient(main.app)
    assert client.get(f"/api/products/{product.id}/core-benchmark").status_code == 200
    assert client.get(f"/api/products/{product.id}/core-benchmark").status_code == 200
    connection = connect(path)
    after = {table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in tables}
    connection.close()
    assert after == before
