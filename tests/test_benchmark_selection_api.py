import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from backend.domain.benchmark_selection import (
    BenchmarkConcurrentWriteError,
    BenchmarkComposition,
    ProductNotOwnedError,
    RelevantQuerySelectionEmptyError,
)
from backend.domain.product import Product, ProductNotFound
from backend.persistence.connection import connect
from backend.persistence.database import initialize_database


def _product(db_path, *, owned):
    with connect(db_path) as connection:
        now = datetime.now(timezone.utc).isoformat()
        cursor = connection.execute(
            "INSERT INTO products(is_owned,created_at,updated_at) VALUES (?,?,?)",
            (owned, now, now),
        )
        return cursor.lastrowid


def test_service_rejects_missing_and_non_owned_products(tmp_path):
    from backend.application.benchmark_selection import BenchmarkSelectionService

    path = tmp_path / "service.db"
    initialize_database(path)
    other = _product(path, owned=False)
    service = BenchmarkSelectionService(db_path=path)
    with pytest.raises(ProductNotFound):
        service.get_benchmark(999)
    with pytest.raises(ProductNotOwnedError):
        service.get_benchmark(other)


def test_service_uses_immediate_boundaries_for_all_three_writes(monkeypatch, tmp_path):
    import backend.application.benchmark_selection as module

    calls = []

    @contextmanager
    def immediate(_path):
        calls.append("immediate")
        yield object()

    owned = Product(1, True, datetime.now(timezone.utc), datetime.now(timezone.utc))
    class Products:
        def __init__(self, _connection): pass
        def get_product(self, _product_id): return owned
        def find_by_external_identity(self, **_kwargs): return Product(2, False, owned.created_at, owned.updated_at)
    class Benchmarks:
        def __init__(self, _connection): pass
        def list_selected_query_ids(self, _product_id): return frozenset({3})
        def replace_relevant_queries(self, product_id, ids): return (product_id, ids)
        def save_benchmark(self, product_id, ids): return (product_id, ids)

    monkeypatch.setattr(module, "immediate_transaction", immediate)
    monkeypatch.setattr(module, "ProductRepository", Products)
    monkeypatch.setattr(module, "BenchmarkSelectionRepository", Benchmarks)
    service = module.BenchmarkSelectionService(db_path=tmp_path / "unused")
    service.replace_relevant_queries(1, (3,))
    service.add_manual_candidate(1, "2")
    service.save_benchmark(1, (2,))
    assert calls == ["immediate", "immediate", "immediate"]


def test_manual_add_checks_relevance_before_identity_mutation(monkeypatch, tmp_path):
    import backend.application.benchmark_selection as module

    touched = False
    owned = Product(1, True, datetime.now(timezone.utc), datetime.now(timezone.utc))
    class Products:
        def __init__(self, _connection): pass
        def get_product(self, _product_id): return owned
        def find_by_external_identity(self, **_kwargs):
            nonlocal touched
            touched = True
    class Benchmarks:
        def __init__(self, _connection): pass
        def list_selected_query_ids(self, _product_id): return frozenset()
    monkeypatch.setattr(module, "ProductRepository", Products)
    monkeypatch.setattr(module, "BenchmarkSelectionRepository", Benchmarks)
    with pytest.raises(RelevantQuerySelectionEmptyError):
        module.BenchmarkSelectionService(db_path=tmp_path / "db").add_manual_candidate(1, "123")
    assert not touched


def test_benchmark_history_survives_relevance_clear_restore(monkeypatch, tmp_path):
    """Clearing relevance blocks writes while benchmark reads remain available."""
    import backend.application.benchmark_selection as module

    selected = False
    owned = Product(1, True, datetime.now(timezone.utc), datetime.now(timezone.utc))
    history = BenchmarkComposition(None, None)
    class Products:
        def __init__(self, _connection): pass
        def get_product(self, _product_id): return owned
    class Benchmarks:
        def __init__(self, _connection): pass
        def list_selected_query_ids(self, _product_id): return frozenset({1}) if selected else frozenset()
        def get_benchmark(self, _product_id): return history
    monkeypatch.setattr(module, "ProductRepository", Products)
    monkeypatch.setattr(module, "BenchmarkSelectionRepository", Benchmarks)
    service = module.BenchmarkSelectionService(db_path=tmp_path / "db")
    assert service.get_benchmark(1) is history
    with pytest.raises(RelevantQuerySelectionEmptyError):
        service.save_benchmark(1, (2,))


def test_only_busy_locked_maps_to_concurrent_write(monkeypatch, tmp_path):
    import backend.application.benchmark_selection as module

    def failing(code):
        @contextmanager
        def boundary(_path):
            error = sqlite3.OperationalError("safe")
            error.sqlite_errorcode = code
            raise error
            yield
        return boundary

    service = module.BenchmarkSelectionService(db_path=tmp_path / "db")
    monkeypatch.setattr(module, "immediate_transaction", failing(sqlite3.SQLITE_BUSY))
    with pytest.raises(BenchmarkConcurrentWriteError):
        service.save_benchmark(1, (2,))
    monkeypatch.setattr(module, "immediate_transaction", failing(sqlite3.SQLITE_ERROR))
    with pytest.raises(sqlite3.OperationalError):
        service.save_benchmark(1, (2,))


def test_pr6_routes_are_exposed():
    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)
    response = client.get("/api/products/0/relevant-queries")
    assert response.status_code == 422
    assert "detail" in response.json()


def test_relevance_and_benchmark_write_transport_shapes(monkeypatch):
    from datetime import date
    from backend import main
    from backend.domain.benchmark_selection import (
        BenchmarkCompositionWriteResult, BenchmarkSet, BenchmarkSetRevision,
        BenchmarkWriteKind, RelevantQueryReadiness, RelevantQuerySelection,
        RelevantQueryWriteResult, SourcePeriod,
    )
    now = datetime.now(timezone.utc)
    period = SourcePeriod(date(2026, 1, 1), date(2026, 1, 31))
    selection = RelevantQuerySelection(1, RelevantQueryReadiness.EMPTY_SELECTION, period, (), 0)
    benchmark_set = BenchmarkSet(2, 1, now)
    revision = BenchmarkSetRevision(3, 2, 1, now, ())
    class Service:
        def replace_relevant_queries(self, *_): return RelevantQueryWriteResult(selection, True)
        def save_benchmark(self, *_): return BenchmarkCompositionWriteResult(BenchmarkWriteKind.CREATED, benchmark_set, revision)
    monkeypatch.setattr(main, "_local_service", lambda: Service())
    relevance = main.put_relevant_queries(1, main.RelevantQueriesRequest(search_query_ids=[]))
    assert relevance["product_id"] == 1 and relevance["changed"] is True and "selection" not in relevance
    response = main.post_benchmark_revision(1, main.BenchmarkRevisionRequest(member_product_ids=[2]))
    assert response.status_code == 201
    assert b'"result":"CREATED"' in response.body and b'"kind"' not in response.body


@pytest.mark.parametrize("value", ["0", "01", "-1", "+1", "abc", " 123", "123 ", "１２３"])
def test_mpstats_probe_sku_requires_canonical_transport_id(value):
    from pydantic import ValidationError
    from backend.main import MPStatsTestRequest
    with pytest.raises(ValidationError):
        MPStatsTestRequest(token="secret", ozon_product_id=value)


def test_mpstats_preview_ids_require_unique_canonical_transport_ids():
    from pydantic import ValidationError
    from backend.main import MPStatsPreviewsRequest
    for values in (["0"], ["01"], ["abc"], ["123", "123"]):
        with pytest.raises(ValidationError):
            MPStatsPreviewsRequest(token="secret", ozon_product_ids=values)
    assert MPStatsPreviewsRequest(token="secret", ozon_product_ids=["456", "123"]).ozon_product_ids == ["456", "123"]


def test_real_testclient_transport_and_exact_local_error_envelopes(monkeypatch):
    from fastapi.testclient import TestClient
    from backend import main
    cases = [
        (ProductNotFound(), 404, "PRODUCT_NOT_FOUND", "Товар не найден."),
        (ProductNotOwnedError(), 409, "PRODUCT_NOT_OWNED", "Выберите свой товар из каталога."),
    ]
    for error_type, (status, code, message) in main.PR6_ERRORS.items():
        if error_type in (ProductNotFound, ProductNotOwnedError):
            continue
        cases.append((error_type(), status, code, message))
    client = TestClient(main.app)
    for error, status, code, message in cases:
        class Service:
            def get_relevant_queries(self, _product_id): raise error
        monkeypatch.setattr(main, "_local_service", lambda: Service())
        response = client.get("/api/products/1/relevant-queries")
        assert response.status_code == status
        assert response.json() == {"error": {"code": code, "message": message}}
    for payload in ({"token":"secret","ozon_product_id":"01"}, {"token":"secret","ozon_product_id":"１２３"}):
        response = client.post("/api/sources/mpstats/test", json=payload)
        assert response.status_code == 422 and "detail" in response.json() and "error" not in response.json()
    response = client.put("/api/products/1/relevant-queries", json={"search_query_ids":["1"]})
    assert response.status_code == 422 and "detail" in response.json()


def test_real_testclient_mpstats_validation_no_call_rate_limit_and_secret_absence(monkeypatch):
    from fastapi.testclient import TestClient
    from backend import main
    calls = []
    class Source:
        def __init__(self, _client): calls.append("source")
    monkeypatch.setattr(main, "MPStatsClient", Source)
    client = TestClient(main.app)
    sentinel = "SECRET_SENTINEL_NEVER_ECHO"
    response = client.post("/api/sources/mpstats/test", json={"token":sentinel,"ozon_product_id":"01"})
    assert response.status_code == 422 and calls == [] and sentinel not in response.text

    class Http:
        def __init__(self, **_kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *_args): pass
    class Service:
        def __init__(self, **_kwargs): pass
        def test_mpstats(self, *_args): raise main.MPStatsRateLimitError(42)
    monkeypatch.setattr(main.httpx, "Client", Http)
    monkeypatch.setattr(main, "BenchmarkSelectionService", Service)
    response = client.post("/api/sources/mpstats/test", json={"token":sentinel,"ozon_product_id":"123"})
    assert response.status_code == 429 and response.headers["Retry-After"] == "42"
    assert response.json()["retry_after_seconds"] == 42 and sentinel not in response.text
