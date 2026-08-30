from fastapi.testclient import TestClient

import backend.main as main
from backend.persistence.connection import transaction
from backend.persistence.database import initialize_database
from backend.persistence.repositories.products import ProductRepository


def test_owned_and_identity_only_workspace_api(monkeypatch, tmp_path):
    path = tmp_path / "api.db"; initialize_database(path)
    monkeypatch.setenv("SCOZ_DB_PATH", str(path)); monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    with transaction(path) as conn:
        product = ProductRepository(conn).resolve_or_create_ozon_product("12345")
        ProductRepository(conn).set_owned(product.id, True)
    with TestClient(main.app) as client:
        owned = client.get("/api/products/owned")
        context = client.get(f"/api/products/{product.id}/workspace-context")
    assert owned.status_code == 200
    assert owned.json()["items"][0]["product_data_status"] == "MISSING"
    assert context.status_code == 200
    assert context.json()["queries"]["readiness"] == "NO_OWN_QUERY_DATA"
    assert context.json()["benchmark"] == {"status":"NOT_CONFIGURED", "revision_id":None, "revision":None, "member_count":0}


def test_workspace_api_exposes_query_evidence_without_product_snapshot(monkeypatch, tmp_path):
    path = tmp_path / "query-api.db"; initialize_database(path)
    monkeypatch.setenv("SCOZ_DB_PATH", str(path)); monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    with transaction(path) as conn:
        product = ProductRepository(conn).resolve_or_create_ozon_product("12345")
        ProductRepository(conn).set_owned(product.id, True)
        conn.execute("INSERT INTO search_queries(query_text,created_at) VALUES ('смеситель','2026-01-01T00:00:00+00:00')")
        conn.execute("INSERT INTO import_batches(source,import_kind,status,started_at) VALUES ('ozon','test','RUNNING','2026-01-01T00:00:00+00:00')")
        conn.execute("INSERT INTO source_artifacts(import_batch_id,artifact_kind,content_sha256,byte_size,created_at) VALUES (1,'test',?,1,'2026-01-01T00:00:00+00:00')", ("b"*64,))
        conn.execute("""INSERT INTO product_query_snapshots(product_id,search_query_id,period_start,period_end,revision,supersedes_snapshot_id,payload_sha256,import_batch_id,source_artifact_id,imported_at,searched_users,seen_users,position_state,average_position,search_to_card_conversion_pct,search_to_order_conversion_pct,ordered_units,ordered_revenue_rub) VALUES (?,1,'2026-01-01','2026-01-31',1,NULL,?,1,1,'2026-02-01T00:00:00+00:00',1,1,'KNOWN',1,'1','1',1,'1')""", (product.id, "a"*64))
    with TestClient(main.app) as client:
        empty = client.get(f"/api/products/{product.id}/workspace-context")
        with transaction(path) as conn:
            conn.execute("INSERT INTO product_relevant_queries(product_id,search_query_id,selected_at) VALUES (?,1,'2026-02-01T00:00:00+00:00')", (product.id,))
        ready = client.get(f"/api/products/{product.id}/workspace-context")
    assert empty.status_code == 200
    assert empty.json()["product"]["product_data_status"] == "MISSING"
    assert empty.json()["queries"]["readiness"] == "EMPTY_SELECTION"
    assert ready.json()["product"]["title"] is None
    assert ready.json()["queries"]["readiness"] == "READY"
