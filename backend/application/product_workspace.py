from pathlib import Path

from backend.domain.benchmark_selection import ProductNotOwnedError
from backend.domain.product import ProductNotFound
from backend.domain.product_workspace import (
    OwnedProductList, ProductCatalogPage, ProductWorkspaceBenchmarkContext,
    ProductWorkspaceContext, WorkspaceBenchmarkStatus,
)
from backend.persistence.connection import transaction
from backend.persistence.repositories.benchmark_selection import BenchmarkSelectionRepository
from backend.persistence.repositories.products import ProductRepository


class ProductWorkspaceService:
    def __init__(self, *, db_path: Path) -> None:
        self._db_path = db_path

    @staticmethod
    def _normalize_query(query: str | None) -> str | None:
        if query is None:
            return None
        normalized = query.strip()
        if not normalized:
            return None
        if len(normalized) > 200:
            raise ValueError("product query too long")
        return normalized

    def list_catalog(self, *, query: str | None, limit: int, offset: int) -> ProductCatalogPage:
        normalized = self._normalize_query(query)
        with transaction(self._db_path) as connection:
            repo = ProductRepository(connection)
            return ProductCatalogPage(repo.list_ozon_products(limit=limit, offset=offset, query=normalized), repo.count_ozon_products(query=normalized), limit, offset)

    def list_owned(self) -> OwnedProductList:
        with transaction(self._db_path) as connection:
            items = ProductRepository(connection).list_owned_ozon_products()
            return OwnedProductList(items, len(items))

    def get_context(self, product_id: int) -> ProductWorkspaceContext:
        with transaction(self._db_path) as connection:
            products = ProductRepository(connection)
            product = products.get_product(product_id)
            if product is None:
                raise ProductNotFound(product_id)
            if not product.is_owned:
                raise ProductNotOwnedError()
            entry = products.get_ozon_product_entry(product_id)
            if entry is None:
                raise ProductNotFound(product_id)
            selections = BenchmarkSelectionRepository(connection)
            queries = selections.get_relevant_query_summary(product_id)
            current = selections.get_benchmark(product_id).current_revision
            benchmark = ProductWorkspaceBenchmarkContext(
                WorkspaceBenchmarkStatus.NOT_CONFIGURED if current is None else WorkspaceBenchmarkStatus.CONFIGURED,
                None if current is None else current.id,
                None if current is None else current.revision,
                0 if current is None else len(current.members),
            )
            return ProductWorkspaceContext(entry, queries, benchmark)
