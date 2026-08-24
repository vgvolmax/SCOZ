from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import SecretStr

from backend.domain.benchmark_selection import (
    BenchmarkCandidate,
    BenchmarkComposition,
    BenchmarkCompositionWriteResult,
    BenchmarkConcurrentWriteError,
    BenchmarkMemberInvalidError,
    CandidatePage,
    ManualCandidateWriteResult,
    ManualOzonSkuInvalidError,
    MPStatsConnectionResult,
    MPStatsProductPreview,
    OwnProductCannotBeCompetitorError,
    PhotoStatus,
    ProductNotOwnedError,
    RelevantQuerySelection,
    RelevantQuerySelectionEmptyError,
    RelevantQuerySelectionInvalidError,
    RelevantQueryWriteResult,
)
from backend.domain.product import Product, ProductNotFound
from backend.persistence.connection import immediate_transaction, transaction
from backend.persistence.repositories.benchmark_selection import BenchmarkSelectionRepository
from backend.persistence.repositories.products import ProductRepository
if TYPE_CHECKING:
    from backend.sources.mpstats import MPStatsClient


class BenchmarkSelectionService:
    def __init__(
        self,
        *,
        db_path: Path,
        mpstats_client: MPStatsClient | None = None,
    ) -> None:
        self._db_path = db_path
        self._mpstats_client = mpstats_client

    @staticmethod
    def _owned_product(repository: ProductRepository, product_id: int) -> Product:
        product = repository.get_product(product_id)
        if product is None:
            raise ProductNotFound(product_id)
        if not product.is_owned:
            raise ProductNotOwnedError()
        return product

    def get_relevant_queries(self, product_id: int) -> RelevantQuerySelection:
        with transaction(self._db_path) as connection:
            self._owned_product(ProductRepository(connection), product_id)
            return BenchmarkSelectionRepository(connection).list_relevant_query_options(product_id)

    def replace_relevant_queries(
        self, product_id: int, search_query_ids: tuple[int, ...]
    ) -> RelevantQueryWriteResult:
        if len(search_query_ids) != len(set(search_query_ids)) or any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in search_query_ids
        ):
            raise RelevantQuerySelectionInvalidError()
        with immediate_transaction(self._db_path) as connection:
            self._owned_product(ProductRepository(connection), product_id)
            return BenchmarkSelectionRepository(connection).replace_relevant_queries(
                product_id, frozenset(search_query_ids)
            )

    def get_candidates(
        self, product_id: int, *, limit: int, offset: int
    ) -> CandidatePage:
        with transaction(self._db_path) as connection:
            self._owned_product(ProductRepository(connection), product_id)
            return BenchmarkSelectionRepository(connection).list_candidates(
                product_id, limit=limit, offset=offset
            )

    def add_manual_candidate(
        self, product_id: int, ozon_product_id: str
    ) -> ManualCandidateWriteResult:
        with immediate_transaction(self._db_path) as connection:
            products = ProductRepository(connection)
            own_product = self._owned_product(products, product_id)
            benchmarks = BenchmarkSelectionRepository(connection)
            if not benchmarks.list_selected_query_ids(product_id):
                raise RelevantQuerySelectionEmptyError()
            if not _canonical_ozon_id(ozon_product_id):
                raise ManualOzonSkuInvalidError()
            product = products.find_by_external_identity(
                source="ozon",
                identity_type="ozon_product_id",
                identity_value=ozon_product_id,
                source_account_scope="",
            )
            created = product is None
            if product is None:
                product = products.resolve_or_create_ozon_product(ozon_product_id)
            if product.id == own_product.id:
                raise OwnProductCannotBeCompetitorError()
            return ManualCandidateWriteResult(
                created=created,
                candidate=BenchmarkCandidate(
                    product_id=product.id,
                    ozon_product_id=ozon_product_id,
                    source_title=None,
                    seller_name=None,
                    contextual_price_rub=None,
                    representative_observed_at=None,
                    matched_relevant_query_count=0,
                    matched_cluster_count=0,
                    best_position=None,
                    photo_status=PhotoStatus.NOT_REQUESTED,
                    photo_url=None,
                    already_selected_in_current_benchmark=False,
                    origin="MANUAL",
                ),
            )

    def get_benchmark(self, product_id: int) -> BenchmarkComposition:
        with transaction(self._db_path) as connection:
            self._owned_product(ProductRepository(connection), product_id)
            return BenchmarkSelectionRepository(connection).get_benchmark(product_id)

    def save_benchmark(
        self, product_id: int, member_product_ids: tuple[int, ...]
    ) -> BenchmarkCompositionWriteResult:
        if len(member_product_ids) != len(set(member_product_ids)) or any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in member_product_ids
        ):
            raise BenchmarkMemberInvalidError()
        try:
            with immediate_transaction(self._db_path) as connection:
                self._owned_product(ProductRepository(connection), product_id)
                repository = BenchmarkSelectionRepository(connection)
                if not repository.list_selected_query_ids(product_id):
                    raise RelevantQuerySelectionEmptyError()
                return repository.save_benchmark(product_id, frozenset(member_product_ids))
        except sqlite3.OperationalError as error:
            if getattr(error, "sqlite_errorcode", None) in (
                sqlite3.SQLITE_BUSY,
                sqlite3.SQLITE_LOCKED,
            ):
                raise BenchmarkConcurrentWriteError() from None
            raise

    def enrich_mpstats_previews(
        self, token: SecretStr, ozon_product_ids: tuple[str, ...]
    ) -> tuple[MPStatsProductPreview, ...]:
        return self._source().get_ozon_product_previews(token, ozon_product_ids)

    def test_mpstats(
        self, token: SecretStr, ozon_product_id: str
    ) -> MPStatsConnectionResult:
        return self._source().test_connection(token, ozon_product_id)

    def _source(self) -> MPStatsClient:
        if self._mpstats_client is None:
            raise RuntimeError("MPStats client is not configured")
        return self._mpstats_client


def _canonical_ozon_id(value: str) -> bool:
    return (
        isinstance(value, str)
        and value.isascii()
        and value.isdigit()
        and int(value) > 0
        and str(int(value)) == value
    )
