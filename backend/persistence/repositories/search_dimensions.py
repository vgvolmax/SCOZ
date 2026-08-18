import sqlite3

from backend.domain.lineage import datetime_from_db, datetime_to_db, utc_now
from backend.domain.search_visibility import Cluster, SearchQuery


def _search_query_from_row(row: sqlite3.Row) -> SearchQuery:
    return SearchQuery(
        id=row["id"],
        query_text=row["query_text"],
        created_at=datetime_from_db(row["created_at"]),
    )


def _cluster_from_row(row: sqlite3.Row) -> Cluster:
    return Cluster(
        id=row["id"],
        name=row["name"],
        created_at=datetime_from_db(row["created_at"]),
    )


def _is_canonical_identity(value: str) -> bool:
    return bool(value) and value == value.strip(" \u00a0")


class SearchDimensionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get_search_query(self, query_id: int) -> SearchQuery | None:
        row = self._conn.execute(
            "SELECT id, query_text, created_at FROM search_queries WHERE id = ?",
            (query_id,),
        ).fetchone()
        return None if row is None else _search_query_from_row(row)

    def resolve_search_query(self, query_text: str) -> SearchQuery:
        if not _is_canonical_identity(query_text):
            raise ValueError("query text must be nonempty canonical source text")
        row = self._conn.execute(
            "SELECT id, query_text, created_at FROM search_queries WHERE query_text = ?",
            (query_text,),
        ).fetchone()
        if row is not None:
            return _search_query_from_row(row)
        cursor = self._conn.execute(
            "INSERT INTO search_queries (query_text, created_at) VALUES (?, ?)",
            (query_text, datetime_to_db(utc_now())),
        )
        result = self.get_search_query(cursor.lastrowid)
        assert result is not None
        return result

    def get_cluster(self, cluster_id: int) -> Cluster | None:
        row = self._conn.execute(
            "SELECT id, name, created_at FROM clusters WHERE id = ?",
            (cluster_id,),
        ).fetchone()
        return None if row is None else _cluster_from_row(row)

    def resolve_cluster(self, name: str) -> Cluster:
        if not _is_canonical_identity(name):
            raise ValueError("cluster name must be nonempty canonical source text")
        row = self._conn.execute(
            "SELECT id, name, created_at FROM clusters WHERE name = ?",
            (name,),
        ).fetchone()
        if row is not None:
            return _cluster_from_row(row)
        cursor = self._conn.execute(
            "INSERT INTO clusters (name, created_at) VALUES (?, ?)",
            (name, datetime_to_db(utc_now())),
        )
        result = self.get_cluster(cursor.lastrowid)
        assert result is not None
        return result
