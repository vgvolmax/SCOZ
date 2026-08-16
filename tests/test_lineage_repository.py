import sqlite3
from dataclasses import fields
from datetime import timezone

import pytest

from backend.domain.lineage import (
    ImportBatch,
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
