import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from backend.config import resolve_db_path


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path if db_path is not None else resolve_db_path()
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
        connection.close()
        raise RuntimeError("SQLite foreign key enforcement could not be enabled")
    return connection


@contextmanager
def transaction(
    db_path: Path | None = None,
) -> Iterator[sqlite3.Connection]:
    path = db_path if db_path is not None else resolve_db_path()
    connection = connect(path)
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
