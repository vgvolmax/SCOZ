import hashlib
import json
import math
import sqlite3
from dataclasses import dataclass

import pytest

from backend.domain.lineage import normalized_payload_sha256


@dataclass(frozen=True)
class InsertResult:
    disposition: str
    row_id: int
    revision: int


def create_observation_fixture(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE synthetic_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            period_start TEXT NOT NULL,
            period_end TEXT NOT NULL,
            real_dimension TEXT NOT NULL,
            revision INTEGER NOT NULL,
            supersedes_snapshot_id INTEGER,
            payload_sha256 TEXT NOT NULL,
            import_batch_id INTEGER NOT NULL,
            source_artifact_id INTEGER,
            imported_at TEXT NOT NULL,
            normalized_value TEXT NOT NULL,
            UNIQUE (product_id, period_start, period_end, real_dimension, revision)
        )
        """
    )


def insert_observation(
    connection: sqlite3.Connection,
    *,
    product_id: int,
    period_start: str,
    period_end: str,
    real_dimension: str,
    payload: dict[str, object],
    import_batch_id: int,
    source_artifact_id: int | None,
    imported_at: str,
) -> InsertResult:
    digest = normalized_payload_sha256(payload)
    previous = connection.execute(
        """
        SELECT id, revision, payload_sha256
        FROM synthetic_observations
        WHERE product_id = ? AND period_start = ? AND period_end = ?
          AND real_dimension = ?
        ORDER BY revision DESC
        LIMIT 1
        """,
        (product_id, period_start, period_end, real_dimension),
    ).fetchone()
    if previous is not None and previous["payload_sha256"] == digest:
        return InsertResult("DUPLICATE", previous["id"], previous["revision"])

    revision = 1 if previous is None else previous["revision"] + 1
    supersedes = None if previous is None else previous["id"]
    cursor = connection.execute(
        """
        INSERT INTO synthetic_observations (
            product_id, period_start, period_end, real_dimension, revision,
            supersedes_snapshot_id, payload_sha256, import_batch_id,
            source_artifact_id, imported_at, normalized_value
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            product_id,
            period_start,
            period_end,
            real_dimension,
            revision,
            supersedes,
            digest,
            import_batch_id,
            source_artifact_id,
            imported_at,
            json.dumps(payload, sort_keys=True),
        ),
    )
    return InsertResult("INSERTED", cursor.lastrowid, revision)


@pytest.fixture
def observations():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    create_observation_fixture(connection)
    try:
        yield connection
    finally:
        connection.close()


def add(observations, payload, **key_overrides):
    key = {
        "product_id": 7,
        "period_start": "2026-08-01",
        "period_end": "2026-08-07",
        "real_dimension": "DAILY",
    }
    key.update(key_overrides)
    return insert_observation(
        observations,
        **key,
        payload=payload,
        import_batch_id=11,
        source_artifact_id=None,
        imported_at="2026-08-16T12:00:00+00:00",
    )


def test_hash_is_key_order_independent_and_preserves_non_ascii():
    first = {"name": "Товар", "values": [1, True, None]}
    second = {"values": [1, True, None], "name": "Товар"}
    digest = normalized_payload_sha256(first)
    assert digest == normalized_payload_sha256(second)
    expected = hashlib.sha256(
        json.dumps(
            first,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    assert digest == expected
    assert len(digest) == 64
    assert digest == digest.lower()


def test_hash_changes_when_normalized_value_changes():
    assert normalized_payload_sha256({"value": 1}) != normalized_payload_sha256({"value": 2})


@pytest.mark.parametrize("non_finite", [math.nan, math.inf, -math.inf])
def test_hash_rejects_non_finite_numbers(non_finite):
    with pytest.raises(ValueError):
        normalized_payload_sha256({"value": non_finite})


def test_same_logical_key_and_hash_is_duplicate_without_row_growth(observations):
    original = add(observations, {"value": 10})
    duplicate = add(observations, {"value": 10})
    assert duplicate == InsertResult("DUPLICATE", original.row_id, 1)
    assert observations.execute("SELECT COUNT(*) FROM synthetic_observations").fetchone()[0] == 1


def test_changed_payload_creates_revision_two_without_mutating_revision_one(observations):
    original = add(observations, {"value": 10})
    before = dict(observations.execute("SELECT * FROM synthetic_observations WHERE id = ?", (original.row_id,)).fetchone())
    statements = []
    observations.set_trace_callback(statements.append)
    corrected = add(observations, {"value": 12})
    observations.set_trace_callback(None)

    rows = observations.execute("SELECT * FROM synthetic_observations ORDER BY revision").fetchall()
    assert corrected.disposition == "INSERTED" and corrected.revision == 2
    assert rows[1]["supersedes_snapshot_id"] == original.row_id
    assert dict(rows[0]) == before
    assert not any(statement.lstrip().upper().startswith("UPDATE") for statement in statements)


def test_exact_new_period_is_a_separate_revision_one_observation(observations):
    add(observations, {"value": 10})
    later = add(
        observations,
        {"value": 10},
        period_start="2026-08-08",
        period_end="2026-08-14",
    )
    assert later.revision == 1
    stored_periods = observations.execute(
        "SELECT period_start, period_end FROM synthetic_observations ORDER BY period_start"
    ).fetchall()
    assert [tuple(row) for row in stored_periods] == [
        ("2026-08-01", "2026-08-07"),
        ("2026-08-08", "2026-08-14"),
    ]


def test_real_dimension_is_key_data_and_is_not_invented_or_merged(observations):
    daily = add(observations, {"value": 10})
    weekly = add(observations, {"value": 10}, real_dimension="WEEKLY")
    assert daily.revision == weekly.revision == 1
    dimensions = observations.execute(
        "SELECT real_dimension FROM synthetic_observations ORDER BY real_dimension"
    ).fetchall()
    assert [row[0] for row in dimensions] == ["DAILY", "WEEKLY"]


def test_missing_real_dimension_is_rejected_instead_of_invented(observations):
    with pytest.raises(TypeError, match="real_dimension"):
        insert_observation(
            observations,
            product_id=7,
            period_start="2026-08-01",
            period_end="2026-08-07",
            payload={"value": 10},
            import_batch_id=11,
            source_artifact_id=None,
            imported_at="2026-08-16T12:00:00+00:00",
        )
    assert observations.execute("SELECT COUNT(*) FROM synthetic_observations").fetchone()[0] == 0
