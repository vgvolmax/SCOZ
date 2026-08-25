from pathlib import Path

from backend.analytics.core_benchmark import calculate_core_benchmark
from backend.domain.benchmark_selection import ProductNotOwnedError
from backend.domain.core_benchmark import (
    BenchmarkRevisionContext, CoreBenchmarkReadiness, CoreBenchmarkResult,
)
from backend.domain.product import ProductNotFound
from backend.persistence.connection import transaction
from backend.persistence.repositories.benchmark_selection import BenchmarkSelectionRepository
from backend.persistence.repositories.product_snapshots import ProductSnapshotRepository
from backend.persistence.repositories.products import ProductRepository


class CoreBenchmarkService:
    def __init__(self, *, db_path: Path) -> None:
        self._db_path = db_path

    def get_core_benchmark(self, product_id: int) -> CoreBenchmarkResult:
        with transaction(self._db_path) as connection:
            connection.execute("BEGIN")
            product = ProductRepository(connection).get_product(product_id)
            if product is None:
                raise ProductNotFound(product_id)
            if not product.is_owned:
                raise ProductNotOwnedError()
            composition = BenchmarkSelectionRepository(connection).get_benchmark(product_id)
            revision = composition.current_revision
            if composition.benchmark_set is None or revision is None:
                return CoreBenchmarkResult(product_id, CoreBenchmarkReadiness.NO_BENCHMARK, None, None, ())
            benchmark = BenchmarkRevisionContext(
                composition.benchmark_set.id, revision.id, revision.revision,
                len(revision.members),
            )
            snapshots = ProductSnapshotRepository(connection)
            own_snapshot = snapshots.find_latest_current_for_product(product_id)
            if own_snapshot is None:
                return CoreBenchmarkResult(product_id, CoreBenchmarkReadiness.NO_OWN_SOURCE_DATA, benchmark, None, ())
            competitor_snapshots = snapshots.list_current_for_products_at_context(
                (member.product_id for member in revision.members),
                own_snapshot.report_generated_on, own_snapshot.report_window_days,
            )
            return calculate_core_benchmark(
                product_id=product_id, composition=composition,
                own_snapshot=own_snapshot,
                competitor_snapshots=competitor_snapshots,
            )
