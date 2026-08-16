from pathlib import Path

from backend.config import resolve_db_path
from backend.persistence.connection import connect
from backend.persistence.migrations.runner import run_migrations


def initialize_database(db_path: Path | None = None) -> None:
    path = db_path if db_path is not None else resolve_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = connect(path)
    try:
        run_migrations(connection)
    finally:
        connection.close()
