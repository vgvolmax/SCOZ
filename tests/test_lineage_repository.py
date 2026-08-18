import sqlite3
import inspect
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
from backend.domain.search_visibility import OzonSearchVisibilityImportSummary
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


def _artifact(repo, batch_id, *, path=None):
    return repo.add_source_artifact(
        batch_id, artifact_kind="xlsx", original_name="report.xlsx",
        content_sha256="a" * 64, byte_size=10, stored_relpath=path,
    )


def test_import_history_item_has_exact_frozen_fields():
    assert [field.name for field in fields(ImportHistoryItem)] == [
        "import_batch_id", "source", "import_kind", "report_type", "status",
        "report_generated_on", "report_window_days", "observed_at", "query_text",
        "cluster_name", "declared_rows", "rows_seen", "rows_accepted", "rows_skipped",
        "duplicate_observations", "new_observations", "corrected_revisions",
        "warnings_count", "row_errors_total", "started_at", "finished_at",
        "source_artifact",
    ]


def test_search_visibility_finish_signature_and_summary_mapping(repository):
    repo, _ = repository
    signature = inspect.signature(repo.finish_ozon_search_visibility_import)
    assert list(signature.parameters) == [
        "batch_id", "status", "observed_at", "query_text", "cluster_name",
        "declared_rows", "rows_seen", "rows_accepted", "rows_skipped",
        "duplicate_observations", "new_observations", "corrected_revisions",
        "warnings_count", "row_errors_total",
    ]
    batch = repo.create_import_batch(source="ozon", import_kind="ozon_search_visibility_xlsx")
    artifact = _artifact(repo, batch.id, path="imports/generated.xlsx")
    observed = datetime(2026, 8, 17, 3, 55, tzinfo=timezone.utc)
    summary = repo.finish_ozon_search_visibility_import(
        batch.id, status=ImportStatus.PARTIAL_SUCCESS, observed_at=observed,
        query_text="exact query", cluster_name="exact cluster", declared_rows=3,
        rows_seen=3, rows_accepted=2, rows_skipped=1, duplicate_observations=1,
        new_observations=1, corrected_revisions=0, warnings_count=2,
        row_errors_total=1,
    )
    assert isinstance(summary, OzonSearchVisibilityImportSummary)
    assert summary.import_batch_id == batch.id and summary.status is ImportStatus.PARTIAL_SUCCESS
    assert summary.observed_at == observed and summary.query_text == "exact query"
    assert summary.cluster_name == "exact cluster" and summary.declared_rows == 3
    assert summary.source_artifact == artifact
    assert summary.started_at.tzinfo == summary.finished_at.tzinfo == timezone.utc


@pytest.mark.parametrize("field", [
    "rows_seen", "rows_accepted", "rows_skipped", "duplicate_observations",
    "new_observations", "corrected_revisions", "warnings_count", "row_errors_total",
])
def test_search_visibility_finish_rejects_negative_counters(repository, field):
    repo, _ = repository
    batch = repo.create_import_batch(source="ozon", import_kind="ozon_search_visibility_xlsx")
    values = dict(status=ImportStatus.SUCCESS, observed_at=None, query_text=None,
        cluster_name=None, declared_rows=None, rows_seen=0, rows_accepted=0,
        rows_skipped=0, duplicate_observations=0, new_observations=0,
        corrected_revisions=0, warnings_count=0, row_errors_total=0)
    values[field] = -1
    with pytest.raises(ValueError, match="non-negative"):
        repo.finish_ozon_search_visibility_import(batch.id, **values)


def test_search_visibility_finish_validates_kind_transition_and_declared_count(repository):
    repo, _ = repository
    wrong = repo.create_import_batch(source="ozon", import_kind="ozon_products_xlsx")
    values = dict(status=ImportStatus.SUCCESS, observed_at=None, query_text=None,
        cluster_name=None, declared_rows=0, rows_seen=0, rows_accepted=0,
        rows_skipped=0, duplicate_observations=0, new_observations=0,
        corrected_revisions=0, warnings_count=0, row_errors_total=0)
    with pytest.raises(ValueError, match="positive"):
        repo.finish_ozon_search_visibility_import(wrong.id, **values)
    values["declared_rows"] = None
    with pytest.raises(InvalidImportStatusTransition):
        repo.finish_ozon_search_visibility_import(wrong.id, **values)
    batch = repo.create_import_batch(source="ozon", import_kind="ozon_search_visibility_xlsx")
    repo.finish_ozon_search_visibility_import(batch.id, **values)
    with pytest.raises(InvalidImportStatusTransition):
        repo.finish_ozon_search_visibility_import(batch.id, **values)


def test_pr4_list_count_and_recovery_are_kind_scoped(repository):
    repo, _ = repository
    running = repo.create_import_batch(source="ozon", import_kind="ozon_search_visibility_xlsx")
    repo.create_import_batch(source="ozon", import_kind="ozon_products_xlsx")
    assert repo.count_ozon_search_visibility_imports() == 1
    assert repo.list_ozon_search_visibility_imports(limit=10, offset=0)[0].import_batch_id == running.id
    finished_at = datetime(2026, 8, 18, tzinfo=timezone(timedelta(hours=3)))
    assert repo.fail_running_ozon_search_visibility_imports(finished_at=finished_at) == 1
    summary = repo.list_ozon_search_visibility_imports(limit=10, offset=0)[0]
    assert summary.status is ImportStatus.FAILED
    assert summary.finished_at == datetime(2026, 8, 17, 21, tzinfo=timezone.utc)
    with pytest.raises(ValueError): repo.list_ozon_search_visibility_imports(limit=0, offset=0)


def test_global_referenced_paths_include_all_kinds_only_under_imports(repository):
    repo, _ = repository
    for index, (kind, path) in enumerate((
        ("ozon_products_xlsx", "imports/pr3.xlsx"),
        ("ozon_search_visibility_xlsx", "imports/pr4.xlsx"),
        ("future", "imports/future.xlsx"),
        ("future", "manual/outside.xlsx"),
        ("future", None),
    )):
        batch = repo.create_import_batch(source="ozon", import_kind=kind)
        _artifact(repo, batch.id, path=path)
    assert repo.list_referenced_archive_paths() == {
        "imports/pr3.xlsx", "imports/pr4.xlsx", "imports/future.xlsx"
    }


def test_unified_history_filters_maps_orders_and_paginates(repository):
    repo, connection = repository
    products = repo.create_import_batch(source="ozon", import_kind="ozon_products_xlsx")
    _artifact(repo, products.id)
    repo.finish_ozon_products_import(
        products.id, status=ImportStatus.SUCCESS, report_generated_on=date(2026, 8, 16),
        report_window_days=7, rows_seen=1, rows_accepted=1, rows_skipped=0,
        duplicate_observations=0, new_observations=1, corrected_revisions=0,
        warnings_count=0, row_errors_total=0,
    )
    visibility = repo.create_import_batch(source="ozon", import_kind="ozon_search_visibility_xlsx")
    _artifact(repo, visibility.id)
    observed = datetime(2026, 8, 17, tzinfo=timezone.utc)
    repo.finish_ozon_search_visibility_import(
        visibility.id, status=ImportStatus.SUCCESS, observed_at=observed,
        query_text="query", cluster_name="cluster", declared_rows=1, rows_seen=1,
        rows_accepted=1, rows_skipped=0, duplicate_observations=0,
        new_observations=1, corrected_revisions=0, warnings_count=0, row_errors_total=0,
    )
    unknown = repo.create_import_batch(source="x", import_kind="future")
    same_started = datetime(2026, 8, 18, tzinfo=timezone.utc).isoformat()
    connection.execute("UPDATE import_batches SET started_at=?", (same_started,))

    assert repo.count_import_history() == 2
    history = repo.list_import_history(limit=10, offset=0)
    assert [item.import_batch_id for item in history] == [visibility.id, products.id]
    assert all(isinstance(item, ImportHistoryItem) for item in history)
    assert history[0].report_type == "OZON_SEARCH_VISIBILITY"
    assert history[0].report_generated_on is None and history[0].observed_at == observed
    assert history[1].report_type == "OZON_PRODUCTS"
    assert history[1].observed_at is None and history[1].report_generated_on == date(2026, 8, 16)
    assert repo.list_import_history(limit=1, offset=1) == [history[1]]
    with pytest.raises(ValueError): repo.list_import_history(limit=101, offset=0)
