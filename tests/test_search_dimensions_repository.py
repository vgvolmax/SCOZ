from backend.persistence.connection import connect
from backend.persistence.database import initialize_database
from backend.persistence.repositories.search_dimensions import SearchDimensionRepository


def test_dimensions_reuse_only_exact_canonical_identity(tmp_path):
    db = tmp_path / "scoz.db"
    initialize_database(db)
    conn = connect(db)
    try:
        repo = SearchDimensionRepository(conn)
        first = repo.resolve_search_query("Точный запрос")
        assert repo.resolve_search_query("Точный запрос") == first
        assert repo.resolve_search_query("точный запрос").id != first.id
        assert repo.resolve_search_query("Точный  запрос").id != first.id
        moscow = repo.resolve_cluster("г. Москва, Россия")
        assert repo.resolve_cluster("г. Москва, Россия") == moscow
        assert repo.resolve_cluster("г. Санкт-Петербург, Россия").id != moscow.id
        assert first.created_at.utcoffset().total_seconds() == 0
    finally:
        conn.close()


def test_dimensions_reject_noncanonical_edges(tmp_path):
    db = tmp_path / "scoz.db"
    initialize_database(db)
    conn = connect(db)
    try:
        repo = SearchDimensionRepository(conn)
        for value in ("", " запрос", "запрос ", "\u00a0запрос", "запрос\u00a0"):
            try:
                repo.resolve_search_query(value)
            except ValueError:
                pass
            else:
                raise AssertionError(value)
    finally:
        conn.close()
