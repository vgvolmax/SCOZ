from dataclasses import fields

from backend.domain.product_workspace import (
    OwnedProductList,
    ProductCatalogPage,
    ProductDataStatus,
    ProductEntry,
    ProductWorkspaceBenchmarkContext,
    ProductWorkspaceContext,
    ProductWorkspaceQueryContext,
    WorkspaceBenchmarkStatus,
)
from backend.domain.benchmark_selection import ProductNotOwnedError, RelevantQueryReadiness
from backend.domain.product import ProductNotFound
from backend.persistence.connection import connect
from backend.persistence.database import initialize_database
from backend.persistence.repositories.products import ProductRepository


def test_product_workspace_domain_contract_is_exact():
    assert [item.value for item in ProductDataStatus] == ["AVAILABLE", "MISSING"]
    assert [item.value for item in WorkspaceBenchmarkStatus] == ["CONFIGURED", "NOT_CONFIGURED"]
    assert [field.name for field in fields(ProductEntry)] == [
        "product_id", "ozon_product_id", "is_owned", "title", "seller_name",
        "brand", "product_data_status", "report_generated_on",
        "report_window_days", "imported_at",
    ]
    assert [field.name for field in fields(ProductWorkspaceQueryContext)] == [
        "readiness", "latest_period", "selected_count",
    ]
    assert [field.name for field in fields(ProductWorkspaceBenchmarkContext)] == [
        "status", "revision_id", "revision", "member_count",
    ]
    assert [field.name for field in fields(ProductWorkspaceContext)] == ["product", "queries", "benchmark"]
    assert [field.name for field in fields(ProductCatalogPage)] == ["items", "total", "limit", "offset"]
    assert [field.name for field in fields(OwnedProductList)] == ["items", "total"]


def _workspace_case(tmp_path, *, query=False, selected=False):
    path = tmp_path / "workspace.db"
    initialize_database(path)
    conn = connect(path)
    product = ProductRepository(conn).resolve_or_create_ozon_product("12345")
    ProductRepository(conn).set_owned(product.id, True)
    if query:
        conn.execute("INSERT INTO search_queries(query_text,created_at) VALUES ('смеситель','2026-01-01T00:00:00+00:00')")
        conn.execute("INSERT INTO import_batches(source,import_kind,status,started_at) VALUES ('ozon','test','RUNNING','2026-01-01T00:00:00+00:00')")
        conn.execute("INSERT INTO source_artifacts(import_batch_id,artifact_kind,content_sha256,byte_size,created_at) VALUES (1,'test',?,1,'2026-01-01T00:00:00+00:00')", ("b"*64,))
        conn.execute("""INSERT INTO product_query_snapshots(product_id,search_query_id,period_start,period_end,revision,supersedes_snapshot_id,payload_sha256,import_batch_id,source_artifact_id,imported_at,searched_users,seen_users,position_state,average_position,search_to_card_conversion_pct,search_to_order_conversion_pct,ordered_units,ordered_revenue_rub) VALUES (?,1,'2026-01-01','2026-01-31',1,NULL,?,1,1,'2026-02-01T00:00:00+00:00',1,1,'KNOWN',1,'1','1',1,'1')""", (product.id, "a"*64))
        if selected:
            conn.execute("INSERT INTO product_relevant_queries(product_id,search_query_id,selected_at) VALUES (?,1,'2026-02-01T00:00:00+00:00')", (product.id,))
    conn.commit(); conn.close()
    return path, product.id


def test_workspace_context_keeps_product_and_query_readiness_independent(tmp_path):
    from backend.application.product_workspace import ProductWorkspaceService
    for selected, expected in ((False, RelevantQueryReadiness.EMPTY_SELECTION), (True, RelevantQueryReadiness.READY)):
        path, product_id = _workspace_case(tmp_path / str(selected), query=True, selected=selected)
        context = ProductWorkspaceService(db_path=path).get_context(product_id)
        assert context.product.product_data_status is ProductDataStatus.MISSING
        assert context.product.title is None and context.product.report_generated_on is None
        assert context.queries.readiness is expected
        assert context.queries.latest_period is not None
        assert context.queries.selected_count == int(selected)
        assert context.benchmark.status is WorkspaceBenchmarkStatus.NOT_CONFIGURED


def test_workspace_identity_only_and_errors(tmp_path):
    from backend.application.product_workspace import ProductWorkspaceService
    path, product_id = _workspace_case(tmp_path)
    service = ProductWorkspaceService(db_path=path)
    assert service.get_context(product_id).queries.readiness is RelevantQueryReadiness.NO_OWN_QUERY_DATA
    assert service.list_owned().total == 1
    assert service.list_catalog(query="   ", limit=50, offset=0).total == 0
    try:
        service.list_catalog(query="x" * 201, limit=50, offset=0)
    except ValueError as error:
        assert str(error) == "product query too long"
    else: raise AssertionError("expected query length failure")
    with __import__('pytest').raises(ProductNotFound): service.get_context(999999)
    conn = connect(path); other = ProductRepository(conn).resolve_or_create_ozon_product("6789"); conn.commit(); conn.close()
    with __import__('pytest').raises(ProductNotOwnedError): service.get_context(other.id)
