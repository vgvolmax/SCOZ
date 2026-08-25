import pytest

from backend.application.core_benchmark import CoreBenchmarkService
from backend.domain.benchmark_selection import ProductNotOwnedError
from backend.domain.core_benchmark import CoreBenchmarkReadiness, CoreBenchmarkResult
from backend.domain.product import ProductNotFound
from backend.persistence.connection import connect
from backend.persistence.database import initialize_database
from backend.persistence.repositories.products import ProductRepository


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "scoz.db"
    initialize_database(path)
    return path


def test_missing_product_raises_product_not_found(db_path):
    with pytest.raises(ProductNotFound):
        CoreBenchmarkService(db_path=db_path).get_core_benchmark(999)


def test_non_owned_product_raises_existing_product_not_owned_error(db_path):
    connection = connect(db_path)
    product = ProductRepository(connection).create_product(is_owned=False)
    connection.commit(); connection.close()
    with pytest.raises(ProductNotOwnedError):
        CoreBenchmarkService(db_path=db_path).get_core_benchmark(product.id)


def test_no_set_returns_no_benchmark(db_path):
    connection = connect(db_path)
    product = ProductRepository(connection).create_product(is_owned=True)
    connection.commit(); connection.close()
    result = CoreBenchmarkService(db_path=db_path).get_core_benchmark(product.id)
    assert result.readiness is CoreBenchmarkReadiness.NO_BENCHMARK
    assert result.benchmark is None and result.observation is None and result.metrics == ()


def test_current_benchmark_without_own_snapshot_returns_no_own_source_data(db_path):
    connection = connect(db_path)
    products = ProductRepository(connection)
    own = products.create_product(is_owned=True)
    competitor = products.create_product(is_owned=False)
    products.add_external_identity(competitor.id, source="ozon", identity_type="ozon_product_id", identity_value="123")
    stamp = "2026-08-24T00:00:00+00:00"
    benchmark_set_id = connection.execute(
        "INSERT INTO benchmark_sets(own_product_id,created_at) VALUES (?,?)", (own.id, stamp)
    ).lastrowid
    revision_id = connection.execute(
        "INSERT INTO benchmark_set_revisions(benchmark_set_id,revision,created_at) VALUES (?,1,?)",
        (benchmark_set_id, stamp),
    ).lastrowid
    connection.execute("INSERT INTO benchmark_members(benchmark_set_revision_id,product_id) VALUES (?,?)",
                       (revision_id, competitor.id))
    connection.commit(); connection.close()
    result = CoreBenchmarkService(db_path=db_path).get_core_benchmark(own.id)
    assert result.readiness is CoreBenchmarkReadiness.NO_OWN_SOURCE_DATA
    assert result.benchmark is not None and result.benchmark.benchmark_member_count == 1
    assert result.observation is None and result.metrics == ()


def test_service_starts_explicit_deferred_read_transaction(monkeypatch, tmp_path):
    from contextlib import contextmanager
    from datetime import datetime, timezone
    from backend.domain.product import Product
    import backend.application.core_benchmark as module

    calls = []
    class Connection:
        def execute(self, sql): calls.append(sql)
    @contextmanager
    def boundary(_path): yield Connection()
    class Products:
        def __init__(self, _connection): pass
        def get_product(self, _id): return Product(1, True, datetime.now(timezone.utc), datetime.now(timezone.utc))
    class Benchmarks:
        def __init__(self, _connection): pass
        def get_benchmark(self, _id):
            from backend.domain.benchmark_selection import BenchmarkComposition
            return BenchmarkComposition(None, None)
    monkeypatch.setattr(module, "transaction", boundary)
    monkeypatch.setattr(module, "ProductRepository", Products)
    monkeypatch.setattr(module, "BenchmarkSelectionRepository", Benchmarks)
    assert module.CoreBenchmarkService(db_path=tmp_path / "unused").get_core_benchmark(1).readiness is CoreBenchmarkReadiness.NO_BENCHMARK
    assert calls == ["BEGIN"]


def test_no_set_and_set_without_revision_return_no_benchmark(db_path):
    connection = connect(db_path); product = ProductRepository(connection).create_product(is_owned=True)
    stamp = "2026-08-24T00:00:00+00:00"
    connection.execute("INSERT INTO benchmark_sets(own_product_id,created_at) VALUES (?,?)", (product.id, stamp))
    connection.commit(); connection.close()
    result = CoreBenchmarkService(db_path=db_path).get_core_benchmark(product.id)
    assert result.readiness is CoreBenchmarkReadiness.NO_BENCHMARK


def test_service_selects_one_anchor_before_loading_competitors(monkeypatch, tmp_path):
    from contextlib import contextmanager
    from datetime import date, datetime, timezone
    from types import SimpleNamespace
    import backend.application.core_benchmark as module
    from backend.domain.benchmark_selection import BenchmarkComposition, BenchmarkMember, BenchmarkSet, BenchmarkSetRevision
    from backend.domain.product import Product

    events = []
    @contextmanager
    def boundary(_path):
        yield SimpleNamespace(execute=lambda sql: events.append(sql))
    class Products:
        def __init__(self, _connection): pass
        def get_product(self, _id): return Product(1, True, datetime.now(timezone.utc), datetime.now(timezone.utc))
    member = BenchmarkMember(2, 10, "10")
    composition = BenchmarkComposition(BenchmarkSet(1, 1, datetime.now(timezone.utc)), BenchmarkSetRevision(2, 1, 1, datetime.now(timezone.utc), (member,)))
    class Benchmarks:
        def __init__(self, _connection): pass
        def get_benchmark(self, _id): return composition
    anchor = SimpleNamespace(id=3, revision=2, report_generated_on=date(2026, 8, 23), report_window_days=28, imported_at=datetime.now(timezone.utc))
    class Snapshots:
        def __init__(self, _connection): pass
        def find_latest_current_for_product(self, _id): events.append("anchor"); return anchor
        def list_current_for_products_at_context(self, ids, generated, window):
            events.append((tuple(ids), generated, window)); return {}
    expected = CoreBenchmarkResult(1, CoreBenchmarkReadiness.NO_COMPATIBLE_SAMPLE, None, None, ())
    monkeypatch.setattr(module, "transaction", boundary); monkeypatch.setattr(module, "ProductRepository", Products)
    monkeypatch.setattr(module, "BenchmarkSelectionRepository", Benchmarks); monkeypatch.setattr(module, "ProductSnapshotRepository", Snapshots)
    monkeypatch.setattr(module, "calculate_core_benchmark", lambda **kwargs: expected)
    assert module.CoreBenchmarkService(db_path=tmp_path / "unused").get_core_benchmark(1) is expected
    assert events == ["BEGIN", "anchor", ((10,), date(2026, 8, 23), 28)]


def test_service_passes_only_current_exact_context_snapshots_to_analytics(monkeypatch, tmp_path):
    import inspect
    import backend.application.core_benchmark as module
    source = inspect.getsource(module.CoreBenchmarkService.get_core_benchmark)
    assert "list_current_for_products_at_context" in source
    assert "competitor_snapshots=competitor_snapshots" in source
    assert "find_current" not in source and "supersedes_snapshot_id" not in source
