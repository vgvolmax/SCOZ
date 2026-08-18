from datetime import timezone

import pytest

from backend.domain.search_visibility import Cluster, SearchQuery
from backend.persistence.connection import connect
from backend.persistence.database import initialize_database
from backend.persistence.repositories.search_dimensions import SearchDimensionRepository


@pytest.fixture
def repository(tmp_path):
    db_path = tmp_path / "scoz.db"
    initialize_database(db_path)
    connection = connect(db_path)
    try:
        yield SearchDimensionRepository(connection)
    finally:
        connection.close()


def test_search_query_exact_identity_is_reused(repository):
    first = repository.resolve_search_query("смеситель для кухни")
    second = repository.resolve_search_query("смеситель для кухни")

    assert first == second
    assert isinstance(first, SearchQuery)
    assert first.query_text == "смеситель для кухни"


@pytest.mark.parametrize(
    "other",
    [
        "смеситель для кухни гибкий",
        "Смеситель для кухни",
        "смеситель  для кухни",
    ],
)
def test_search_query_similar_text_remains_a_separate_identity(repository, other):
    original = repository.resolve_search_query("смеситель для кухни")
    distinct = repository.resolve_search_query(other)

    assert distinct.id != original.id
    assert distinct.query_text == other


@pytest.mark.parametrize(
    "invalid",
    ["", " запрос", "запрос ", "\u00a0запрос", "запрос\u00a0", " ", "\u00a0"],
)
def test_search_query_rejects_noncanonical_callers(repository, invalid):
    with pytest.raises(ValueError, match="canonical"):
        repository.resolve_search_query(invalid)


def test_cluster_exact_identity_is_reused_without_aliasing(repository):
    moscow = repository.resolve_cluster("г. Москва, Россия")

    assert repository.resolve_cluster("г. Москва, Россия") == moscow
    assert repository.resolve_cluster("г. Санкт-Петербург, Россия").id != moscow.id
    assert repository.resolve_cluster("г. москва, Россия").id != moscow.id
    assert repository.resolve_cluster("Москва").id != moscow.id


@pytest.mark.parametrize(
    "invalid",
    ["", " Москва", "Москва ", "\u00a0Москва", "Москва\u00a0", " ", "\u00a0"],
)
def test_cluster_rejects_noncanonical_callers(repository, invalid):
    with pytest.raises(ValueError, match="canonical"):
        repository.resolve_cluster(invalid)


def test_getters_map_domain_objects_with_utc_creation_and_missing_is_none(repository):
    query = repository.resolve_search_query("точный запрос")
    cluster = repository.resolve_cluster("г. Москва, Россия")

    assert repository.get_search_query(query.id) == query
    assert repository.get_cluster(cluster.id) == cluster
    assert isinstance(query, SearchQuery)
    assert isinstance(cluster, Cluster)
    assert query.created_at.tzinfo == timezone.utc
    assert cluster.created_at.tzinfo == timezone.utc
    assert repository.get_search_query(999_999) is None
    assert repository.get_cluster(999_999) is None
