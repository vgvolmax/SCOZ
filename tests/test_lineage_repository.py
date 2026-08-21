import sqlite3
from dataclasses import fields
from datetime import date, datetime, timedelta, timezone

import pytest

from backend.domain.lineage import (
    ImportBatch,
    ImportHistoryItem,
    ImportBatchNotFound,
    ImportStatus,
    InvalidImportStatusTransition,
    InvalidSourceArtifactMetadata,
    InvalidStoredRelativePath,
    SourceArtifact,
)
from backend.persistence.connection import connect
from backend.persistence.database import initialize_database
from backend.persistence.repositories.lineage import LineageRepository


@pytest.fixture
def repository(tmp_path):
    path = tmp_path / "scoz.db"
    initialize_database(path)
    connection = connect(path)
    try:
        yield LineageRepository(connection), connection
    finally:
        connection.close()


def test_batch_lifecycle_and_nullable_get(repository):
    repo, _ = repository
    batch = repo.create_import_batch(source="ozon", import_kind="report")
    assert isinstance(batch, ImportBatch)
    assert batch.status is ImportStatus.RUNNING
    assert batch.finished_at is None
    assert batch.started_at.tzinfo == timezone.utc
    assert repo.get_import_batch(batch.id) == batch
    assert repo.get_import_batch(999999) is None
    with pytest.raises(ImportBatchNotFound):
        repo.finish_import_batch(999999, status=ImportStatus.SUCCESS)


@pytest.mark.parametrize("status", list(ImportStatus)[1:])
def test_each_terminal_transition_is_allowed_once(repository, status):
    repo, _ = repository
    batch = repo.create_import_batch(source="ozon", import_kind="report")
    finished = repo.finish_import_batch(batch.id, status=status)
    assert finished.status is status
    assert finished.finished_at is not None
    assert finished.finished_at.tzinfo == timezone.utc
    for next_status in ImportStatus:
        with pytest.raises(InvalidImportStatusTransition):
            repo.finish_import_batch(batch.id, status=next_status)


def test_running_to_running_is_rejected(repository):
    repo, _ = repository
    batch = repo.create_import_batch(source="ozon", import_kind="report")
    with pytest.raises(InvalidImportStatusTransition):
        repo.finish_import_batch(batch.id, status=ImportStatus.RUNNING)


def test_artifact_round_trip_nullable_values_and_missing_get(repository):
    repo, _ = repository
    batch = repo.create_import_batch(source="file", import_kind="sales")
    artifact = repo.add_source_artifact(
        batch.id, artifact_kind="xlsx", original_name=None,
        content_sha256="a" * 64, byte_size=0, stored_relpath=None,
    )
    assert isinstance(artifact, SourceArtifact)
    assert artifact.import_batch_id == batch.id
    assert artifact.original_name is None and artifact.stored_relpath is None
    assert artifact.created_at.tzinfo == timezone.utc
    assert repo.get_source_artifact(artifact.id) == artifact
    assert repo.get_source_artifact(999999) is None


def test_artifact_full_non_null_round_trip(repository):
    repo, _ = repository
    batch = repo.create_import_batch(source="ozon", import_kind="query-report")
    artifact = repo.add_source_artifact(
        batch.id,
        artifact_kind="xlsx",
        original_name="query analytics.xlsx",
        content_sha256="0123456789abcdef" * 4,
        byte_size=12_345,
        stored_relpath="imports/query-analytics.xlsx",
    )

    assert artifact.import_batch_id == batch.id
    assert artifact.artifact_kind == "xlsx"
    assert artifact.original_name == "query analytics.xlsx"
    assert artifact.content_sha256 == "0123456789abcdef" * 4
    assert artifact.byte_size == 12_345
    assert artifact.stored_relpath == "imports/query-analytics.xlsx"
    assert artifact.created_at.tzinfo == timezone.utc
    assert repo.get_source_artifact(artifact.id) == artifact


@pytest.mark.parametrize("byte_size,digest", [(-1, "a" * 64), (1, "A" * 64), (1, "a" * 63), (1, "g" * 64)])
def test_invalid_metadata_precedes_paths_and_parent(repository, byte_size, digest):
    repo, connection = repository
    with pytest.raises(InvalidSourceArtifactMetadata):
        repo.add_source_artifact(999999, artifact_kind="xlsx", original_name=None,
                                 content_sha256=digest, byte_size=byte_size,
                                 stored_relpath="../bad")
    assert connection.execute("SELECT COUNT(*) FROM source_artifacts").fetchone()[0] == 0


@pytest.mark.parametrize("path", ["", "/file.xlsx", r"C:\file.xlsx", "C:file.xlsx", r"\\server\share\file.xlsx", "../file.xlsx", "reports/../file.xlsx", "reports/a/../../file.xlsx"])
def test_invalid_stored_paths_precede_missing_parent(repository, path):
    repo, connection = repository
    with pytest.raises(InvalidStoredRelativePath):
        repo.add_source_artifact(999999, artifact_kind="xlsx", original_name=None,
                                 content_sha256="a" * 64, byte_size=1,
                                 stored_relpath=path)
    assert connection.execute("SELECT COUNT(*) FROM source_artifacts").fetchone()[0] == 0


@pytest.mark.parametrize("path", ["reports/report..final.xlsx", "reports/version..2/file.xlsx", "foo..bar"])
def test_two_dots_inside_component_are_valid(repository, path):
    repo, _ = repository
    batch = repo.create_import_batch(source="file", import_kind="sales")
    assert repo.add_source_artifact(batch.id, artifact_kind="xlsx", original_name="x",
                                    content_sha256="b" * 64, byte_size=1,
                                    stored_relpath=path).stored_relpath == path


def test_missing_batch_is_named_error(repository):
    repo, _ = repository
    with pytest.raises(ImportBatchNotFound):
        repo.add_source_artifact(999999, artifact_kind="xlsx", original_name=None,
                                 content_sha256="a" * 64, byte_size=1)


def test_database_constraints_are_defense_in_depth(repository):
    _, connection = repository
    now = "2026-08-16T00:00:00+00:00"
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("INSERT INTO source_artifacts (import_batch_id, artifact_kind, content_sha256, byte_size, created_at) VALUES (999, 'x', ?, 1, ?)", ("a" * 64, now))
    batch_id = connection.execute("INSERT INTO import_batches (source, import_kind, status, started_at) VALUES ('x', 'x', 'RUNNING', ?)", (now,)).lastrowid
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute("INSERT INTO source_artifacts (import_batch_id, artifact_kind, content_sha256, byte_size, created_at) VALUES (?, 'x', ?, -1, ?)", (batch_id, "a" * 64, now))


def test_narrow_boundary_and_no_rows_leak(repository):
    repo, connection = repository
    batch = repo.create_import_batch(source="x", import_kind="x")
    artifact = repo.add_source_artifact(batch.id, artifact_kind="x", original_name=None,
                                        content_sha256="a" * 64, byte_size=1)
    assert not isinstance(batch, sqlite3.Row) and not isinstance(artifact, sqlite3.Row)
    assert [f.name for f in fields(ImportBatch)] == ["id", "source", "import_kind", "status", "started_at", "finished_at"]
    assert [f.name for f in fields(SourceArtifact)] == ["id", "import_batch_id", "artifact_kind", "original_name", "content_sha256", "byte_size", "stored_relpath", "created_at"]
    assert connection.in_transaction
    connection.rollback()


def test_search_visibility_finish_and_unified_history(repository):
    repo, _ = repository
    batch = repo.create_import_batch(source="ozon", import_kind="ozon_search_visibility_xlsx")
    artifact = repo.add_source_artifact(
        batch.id, artifact_kind="ozon_search_visibility_xlsx",
        original_name="visibility.xlsx", content_sha256="c" * 64, byte_size=42,
        stored_relpath="imports/visibility.xlsx",
    )
    observed_at = datetime(2026, 8, 17, 9, 30, tzinfo=timezone.utc)
    summary = repo.finish_ozon_search_visibility_import(
        batch.id, status=ImportStatus.PARTIAL_SUCCESS, observed_at=observed_at,
        query_text="синтетический запрос", cluster_name="Москва",
        declared_rows=3, rows_seen=3, rows_accepted=2, rows_skipped=1,
        duplicate_observations=0, new_observations=2,
        corrected_revisions=0, warnings_count=0, row_errors_total=1,
    )
    assert summary.observed_at == observed_at
    assert summary.query_text == "синтетический запрос"
    assert summary.cluster_name == "Москва" and summary.declared_rows == 3
    assert summary.source_artifact == artifact
    assert repo.count_ozon_search_visibility_imports() == 1
    history = repo.list_import_history(limit=10, offset=0)
    assert len(history) == 1 and isinstance(history[0], ImportHistoryItem)
    assert history[0].report_type == "OZON_SEARCH_VISIBILITY"
    assert history[0].report_generated_on is None
    assert history[0].observed_at == observed_at
    assert repo.list_referenced_archive_paths() == {"imports/visibility.xlsx"}
    with pytest.raises(InvalidImportStatusTransition):
        repo.finish_ozon_search_visibility_import(
            batch.id, status=ImportStatus.SUCCESS, observed_at=observed_at,
            query_text="q", cluster_name="c", declared_rows=1, rows_seen=1,
            rows_accepted=1, rows_skipped=0, duplicate_observations=0,
            new_observations=1, corrected_revisions=0, warnings_count=0,
            row_errors_total=0,
        )


def test_unified_history_filters_unknown_and_global_archive_references(repository):
    repo, connection = repository
    products = repo.create_import_batch(source="ozon", import_kind="ozon_products_xlsx")
    unknown = repo.create_import_batch(source="other", import_kind="future")
    repo.add_source_artifact(products.id, artifact_kind="xlsx", original_name=None,
                             content_sha256="d" * 64, byte_size=1,
                             stored_relpath="imports/products.xlsx")
    repo.add_source_artifact(unknown.id, artifact_kind="xlsx", original_name=None,
                             content_sha256="e" * 64, byte_size=1,
                             stored_relpath="outside/future.xlsx")
    assert repo.count_import_history() == 1
    assert repo.list_import_history(limit=10, offset=0)[0].report_type == "OZON_PRODUCTS"
    assert repo.list_referenced_archive_paths() == {"imports/products.xlsx"}
    assert repo.fail_running_ozon_search_visibility_imports(
        finished_at=datetime.now(timezone.utc)
    ) == 0
    assert connection.in_transaction


def _finish_pr5(repo, kind, *, status=ImportStatus.SUCCESS):
    batch = repo.create_import_batch(source="ozon", import_kind=kind)
    common = dict(status=status, period_start=date(2026, 7, 1),
                  period_end=date(2026, 7, 31), rows_seen=2, rows_accepted=2,
                  rows_skipped=0, duplicate_observations=0, new_observations=2,
                  corrected_revisions=0, warnings_count=0, row_errors_total=0)
    if kind == "ozon_seller_queries_xlsx":
        return repo.finish_ozon_seller_queries_import(
            batch.id, generated_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
            product_ozon_id="123456", **common)
    return repo.finish_ozon_query_metrics_import(
        batch.id, sort_context="Сортировка: По убыванию в Популярность запроса", **common)


def test_pr5_finish_summaries_and_mixed_history_context(repository):
    repo, _ = repository
    seller = _finish_pr5(repo, "ozon_seller_queries_xlsx")
    metrics = _finish_pr5(repo, "ozon_query_metrics_xlsx", status=ImportStatus.PARTIAL_SUCCESS)
    assert seller.product_ozon_id == "123456"
    assert seller.generated_at == datetime(2026, 8, 1, tzinfo=timezone.utc)
    assert metrics.sort_context == "Сортировка: По убыванию в Популярность запроса"
    history = repo.list_import_history(limit=10, offset=0)
    assert repo.count_import_history() == 2
    assert [item.report_type for item in history] == ["OZON_QUERY_METRICS", "OZON_OWN_PRODUCT_QUERIES"]
    assert history[0].report_generated_at is None
    assert history[0].report_product_ozon_id is None
    assert history[1].sort_context is None
    assert history[1].query_text is None


@pytest.mark.parametrize("kind", ["ozon_seller_queries_xlsx", "ozon_query_metrics_xlsx"])
def test_pr5_finish_rejects_invalid_context_and_wrong_kind(repository, kind):
    repo, _ = repository
    batch = repo.create_import_batch(source="ozon", import_kind=kind)
    common = dict(status=ImportStatus.SUCCESS, period_start=date(2026, 8, 2),
                  period_end=date(2026, 8, 1), rows_seen=0, rows_accepted=0,
                  rows_skipped=0, duplicate_observations=0, new_observations=0,
                  corrected_revisions=0, warnings_count=0, row_errors_total=0)
    with pytest.raises(ValueError, match="period"):
        if kind == "ozon_seller_queries_xlsx":
            repo.finish_ozon_seller_queries_import(
                batch.id, generated_at=None, product_ozon_id="123", **common)
        else:
            repo.finish_ozon_query_metrics_import(batch.id, sort_context=None, **common)

@pytest.mark.parametrize("status", [ImportStatus.SUCCESS, ImportStatus.PARTIAL_SUCCESS])
@pytest.mark.parametrize("missing", ["generated_at", "period_start", "period_end", "product_ozon_id"])
def test_successful_seller_finish_requires_complete_canonical_context(repository, status, missing):
    repo, _ = repository
    batch = repo.create_import_batch(source="ozon", import_kind="ozon_seller_queries_xlsx")
    values = dict(generated_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
                  period_start=date(2026, 7, 1), period_end=date(2026, 7, 31),
                  product_ozon_id="123")
    values[missing] = None
    with pytest.raises(ValueError):
        repo.finish_ozon_seller_queries_import(batch.id, status=status,
            rows_seen=0, rows_accepted=0, rows_skipped=0, duplicate_observations=0,
            new_observations=0, corrected_revisions=0, warnings_count=0,
            row_errors_total=0, **values)

@pytest.mark.parametrize("status", [ImportStatus.SUCCESS, ImportStatus.PARTIAL_SUCCESS])
@pytest.mark.parametrize("missing", ["period_start", "period_end", "sort_context"])
def test_successful_metrics_finish_requires_complete_canonical_context(repository, status, missing):
    repo, _ = repository
    batch = repo.create_import_batch(source="ozon", import_kind="ozon_query_metrics_xlsx")
    values = dict(period_start=date(2026, 7, 1), period_end=date(2026, 7, 31),
                  sort_context="Сортировка: По убыванию в Популярность запроса")
    values[missing] = None
    with pytest.raises(ValueError):
        repo.finish_ozon_query_metrics_import(batch.id, status=status,
            rows_seen=0, rows_accepted=0, rows_skipped=0, duplicate_observations=0,
            new_observations=0, corrected_revisions=0, warnings_count=0,
            row_errors_total=0, **values)

def test_failed_pr5_finish_allows_absent_context(repository):
    repo, _ = repository
    seller = repo.create_import_batch(source="ozon", import_kind="ozon_seller_queries_xlsx")
    assert repo.finish_ozon_seller_queries_import(
        seller.id, status=ImportStatus.FAILED, generated_at=None, period_start=None,
        period_end=None, product_ozon_id=None, rows_seen=0, rows_accepted=0,
        rows_skipped=0, duplicate_observations=0, new_observations=0,
        corrected_revisions=0, warnings_count=0, row_errors_total=0).status is ImportStatus.FAILED
    metrics = repo.create_import_batch(source="ozon", import_kind="ozon_query_metrics_xlsx")
    assert repo.finish_ozon_query_metrics_import(
        metrics.id, status=ImportStatus.FAILED, period_start=None, period_end=None,
        sort_context=None, rows_seen=0, rows_accepted=0, rows_skipped=0,
        duplicate_observations=0, new_observations=0, corrected_revisions=0,
        warnings_count=0, row_errors_total=0).status is ImportStatus.FAILED


def test_pr5_availability_is_global_and_failed_later_does_not_reset(repository):
    repo, _ = repository
    assert repo.get_pr5_source_availability() == {
        "own_product_queries": False, "query_metrics": False}
    _finish_pr5(repo, "ozon_seller_queries_xlsx")
    for index in range(55):
        batch = repo.create_import_batch(source="other", import_kind="ozon_products_xlsx")
        repo.finish_import_batch(batch.id, status=ImportStatus.FAILED)
    failed = repo.create_import_batch(source="ozon", import_kind="ozon_seller_queries_xlsx")
    repo.finish_import_batch(failed.id, status=ImportStatus.FAILED)
    assert all(item.report_type != "OZON_OWN_PRODUCT_QUERIES"
               or item.status is ImportStatus.FAILED
               for item in repo.list_import_history(limit=50, offset=0))
    assert repo.get_pr5_source_availability() == {
        "own_product_queries": True, "query_metrics": False}
    assert repo.list_import_history(limit=1, offset=20)


def test_pr5_recovery_is_kind_scoped_and_idempotent(repository):
    repo, _ = repository
    seller = repo.create_import_batch(source="ozon", import_kind="ozon_seller_queries_xlsx")
    metrics = repo.create_import_batch(source="ozon", import_kind="ozon_query_metrics_xlsx")
    finished_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    assert repo.fail_running_ozon_seller_queries_imports(finished_at=finished_at) == 1
    assert repo.fail_running_ozon_seller_queries_imports(finished_at=finished_at) == 0
    assert repo.get_import_batch(seller.id).status is ImportStatus.FAILED
    assert repo.get_import_batch(metrics.id).status is ImportStatus.RUNNING
    assert repo.fail_running_ozon_query_metrics_imports(finished_at=finished_at) == 1
