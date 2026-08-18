import sqlite3

from backend.domain.lineage import datetime_from_db, datetime_to_db, utc_now
from backend.domain.search_visibility import Cluster, SearchQuery


class SearchDimensionRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    @staticmethod
    def _validate(value: str) -> None:
        if not isinstance(value, str) or not value or value != value.strip(" \u00a0"):
            raise ValueError("identity must be nonempty canonical source text")

    def get_search_query(self, query_id: int) -> SearchQuery | None:
        row = self._conn.execute(
            "SELECT id, query_text, created_at FROM search_queries WHERE id=?", (query_id,)
        ).fetchone()
        return None if row is None else SearchQuery(row["id"], row["query_text"], datetime_from_db(row["created_at"]))

    def resolve_search_query(self, query_text: str) -> SearchQuery:
        self._validate(query_text)
        row = self._conn.execute("SELECT id FROM search_queries WHERE query_text=?", (query_text,)).fetchone()
        if row is not None:
            result = self.get_search_query(row["id"])
            assert result is not None
            return result
        cursor = self._conn.execute(
            "INSERT INTO search_queries(query_text,created_at) VALUES (?,?)",
            (query_text, datetime_to_db(utc_now())),
        )
        result = self.get_search_query(cursor.lastrowid)
        assert result is not None
        return result

    def get_cluster(self, cluster_id: int) -> Cluster | None:
        row = self._conn.execute(
            "SELECT id, name, created_at FROM clusters WHERE id=?", (cluster_id,)
        ).fetchone()
        return None if row is None else Cluster(row["id"], row["name"], datetime_from_db(row["created_at"]))

    def resolve_cluster(self, name: str) -> Cluster:
        self._validate(name)
        row = self._conn.execute("SELECT id FROM clusters WHERE name=?", (name,)).fetchone()
        if row is not None:
            result = self.get_cluster(row["id"])
            assert result is not None
            return result
        cursor = self._conn.execute(
            "INSERT INTO clusters(name,created_at) VALUES (?,?)",
            (name, datetime_to_db(utc_now())),
        )
        result = self.get_cluster(cursor.lastrowid)
        assert result is not None
        return result
