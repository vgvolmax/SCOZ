from fastapi.testclient import TestClient

import backend.main as main
from backend.persistence.database import initialize_database
from tests.xlsx_factory import build_ozon_products_workbook


def _client(monkeypatch, tmp_path):
    db_path = tmp_path / "scoz.db"
    initialize_database(db_path)
    monkeypatch.setenv("SCOZ_DB_PATH", str(db_path))
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    return TestClient(main.app)


def test_post_valid_workbook_returns_exact_success_result(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path) as client:
        response = client.post("/api/imports/ozon-products", files={"file": ("report.xlsx", build_ozon_products_workbook(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"import_batch_id", "report_type", "status", "report_generated_on", "report_window_days", "rows_seen", "rows_accepted", "rows_skipped", "duplicate_observations", "new_observations", "corrected_revisions", "warnings_count", "row_errors_total", "row_errors", "row_errors_truncated", "source_artifact", "imported_at", "readiness"}
    assert body["report_type"] == "OZON_PRODUCTS" and body["status"] == "SUCCESS"
    assert body["rows_accepted"] == 1 and body["readiness"] == "SELECT_OWN_PRODUCTS"


def test_transport_media_type_and_missing_file_are_distinct(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path) as client:
        wrong = client.post("/api/imports/ozon-products", content=b"not multipart", headers={"content-type": "application/octet-stream"})
        missing = client.post("/api/imports/ozon-products", files={"wrong": ("x.xlsx", b"x")})
    assert wrong.status_code == 415
    assert wrong.json() == {"error": {"code": "UNSUPPORTED_UPLOAD_MEDIA_TYPE", "message": "Выберите XLSX-файл."}, "result": None}
    assert missing.status_code == 422


def test_products_ownership_and_history_are_functional(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path) as client:
        client.post("/api/imports/ozon-products", files={"file": ("report.xlsx", build_ozon_products_workbook(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        products = client.get("/api/products").json()
        assert products["total"] == 1 and products["items"][0]["ozon_product_id"] == "100000001"
        product_id = products["items"][0]["id"]
        assert client.patch(f"/api/products/{product_id}/ownership", json={"is_owned": True}).status_code == 200
        assert client.get("/api/products").json()["readiness"] == "READY"
        history = client.get("/api/imports").json()
        assert history["total"] == 1 and history["items"][0]["rows_accepted"] == 1
        assert client.patch(f"/api/products/{product_id}/ownership", json={"is_owned": "true"}).status_code == 422
        assert client.patch("/api/products/999999/ownership", json={"is_owned": True}).status_code == 404
