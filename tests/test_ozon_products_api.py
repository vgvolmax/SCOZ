from fastapi.testclient import TestClient
from io import BytesIO

import backend.main as main
import backend.application.ozon_products_import as service
from backend.application.import_runtime import IMPORT_LOCK
from backend.domain.lineage import ImportStatus
from backend.persistence.connection import transaction
from backend.persistence.database import initialize_database
from backend.persistence.repositories.lineage import LineageRepository
from backend.persistence.repositories.product_snapshots import ProductSnapshotRepository
from backend.persistence.repositories.products import ProductRepository
from tests.xlsx_factory import OZON_PRODUCTS_HEADERS, _default_row, build_ozon_products_workbook


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
        assert type(products["items"][0]["is_owned"]) is bool
        product_id = products["items"][0]["id"]
        patched = client.patch(f"/api/products/{product_id}/ownership", json={"is_owned": True})
        assert patched.status_code == 200 and type(patched.json()["is_owned"]) is bool
        assert client.get("/api/products").json()["readiness"] == "READY"
        history = client.get("/api/imports").json()
        assert history["total"] == 1 and history["items"][0]["rows_accepted"] == 1
        assert client.patch(f"/api/products/{product_id}/ownership", json={"is_owned": "true"}).status_code == 422
        assert client.patch("/api/products/999999/ownership", json={"is_owned": True}).status_code == 404


def test_visibility_only_product_is_excluded_until_products_report(monkeypatch, tmp_path):
    db_path = tmp_path / "scoz.db"
    initialize_database(db_path)
    with transaction(db_path) as conn:
        product = ProductRepository(conn).resolve_or_create_ozon_product("100000001")
        ProductRepository(conn).set_owned(product.id, True)

    with _client(monkeypatch, tmp_path) as client:
        assert client.get("/api/products").json() == {
            "items": [], "total": 0, "readiness": "SELECT_OWN_PRODUCTS"
        }
        assert _post(client, build_ozon_products_workbook()).status_code == 200
        body = client.get("/api/products").json()

    assert body["total"] == 1
    assert body["items"][0]["id"] == product.id
    assert body["items"][0]["is_owned"] is True


def _post(client, data, *, filename="report.xlsx"):
    return client.post(
        "/api/imports/ozon-products",
        files={"file": (filename, data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )


def _assert_sanitized(response, secret=b"uploaded-secret"):
    body = response.content.lower()
    assert b"traceback" not in body
    assert str(response.request.url).encode().lower() not in body
    assert secret.lower() not in body


def test_post_partial_success_is_http_200_not_207(monkeypatch, tmp_path):
    valid = _default_row("Синтетическая категория")
    invalid = dict(valid); invalid[OZON_PRODUCTS_HEADERS[1]] = "bad"
    with _client(monkeypatch, tmp_path) as client:
        response = _post(client, build_ozon_products_workbook(rows=[valid, invalid]))
    assert response.status_code == 200 and response.status_code != 207
    assert response.json()["status"] == "PARTIAL_SUCCESS"


def test_post_zero_usable_rows_returns_422_with_failed_lineage(monkeypatch, tmp_path):
    invalid = _default_row("Синтетическая категория")
    invalid[OZON_PRODUCTS_HEADERS[1]] = "bad"
    with _client(monkeypatch, tmp_path) as client:
        response = _post(client, build_ozon_products_workbook(rows=[invalid]))
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == {"code": "INVALID_METRIC_VALUE", "message": "Некорректное значение показателя."}
    assert body["result"] is not None and body["result"]["status"] == "FAILED"
    with transaction(tmp_path / "scoz.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM product_snapshots").fetchone()[0] == 0
        batch = conn.execute("SELECT status FROM import_batches").fetchone()
        artifact = conn.execute("SELECT stored_relpath FROM source_artifacts").fetchone()
    assert batch["status"] == "FAILED"
    assert artifact["stored_relpath"] is None


def test_post_validation_error_matrix(monkeypatch, tmp_path):
    cases = [
        (build_ozon_products_workbook(marker_overrides={"A1": "Другой отчёт"}), "WRONG_REPORT_TYPE", "Выберите отчёт Ozon «Товары на Ozon».", 422),
        (build_ozon_products_workbook(marker_overrides={"A6": "wrong"}), "INCOMPATIBLE_REPORT_SCHEMA", "Версия или структура отчёта не поддерживается.", 422),
        (build_ozon_products_workbook(generated_on="bad"), "INVALID_REPORT_PERIOD", "Не удалось прочитать дату формирования или период отчёта.", 422),
        (b"uploaded-secret", "UNSUPPORTED_WORKBOOK", "Не удалось прочитать XLSX-файл.", 422),
    ]
    with _client(monkeypatch, tmp_path) as client:
        for payload, code, message, status in cases:
            response = _post(client, payload)
            assert response.status_code == status
            assert response.json()["error"] == {"code": code, "message": message}
            _assert_sanitized(response)


def test_post_too_large_and_concurrent_lock(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path) as client:
        too_large = _post(client, b"x" * (service.MAX_UPLOAD_BYTES + 1))
        assert too_large.status_code == 413
        assert too_large.json()["result"] is None
        IMPORT_LOCK.acquire()
        try:
            conflict = _post(client, build_ozon_products_workbook())
        finally:
            IMPORT_LOCK.release()
    assert conflict.status_code == 409
    assert conflict.json()["result"] is None


def test_persistence_failure_returns_500_with_failed_result(monkeypatch, tmp_path):
    monkeypatch.setattr(
        ProductSnapshotRepository,
        "resolve_revision",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("uploaded-secret")),
    )
    with _client(monkeypatch, tmp_path) as client:
        response = _post(client, build_ozon_products_workbook())
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "IMPORT_PERSISTENCE_ERROR"
    assert response.json()["result"]["status"] == "FAILED"
    _assert_sanitized(response)


def test_latest_product_observation_orders_date_window_revision(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path) as client:
        row = _default_row("Синтетическая категория")
        changed = dict(row); changed[OZON_PRODUCTS_HEADERS[0]] = "revision two"
        _post(client, build_ozon_products_workbook(rows=[row]))
        _post(client, build_ozon_products_workbook(rows=[changed]))
        _post(client, build_ozon_products_workbook(rows=[row], window_label="28 дней"))
        product = client.get("/api/products").json()["items"][0]
        assert product["report_generated_on"] == "2026-08-16"
        assert product["report_window_days"] == 28
        assert product["revision"] == 1
        _post(client, build_ozon_products_workbook(rows=[row], generated_on="08.17.26"))
        product = client.get("/api/products").json()["items"][0]
        assert product["report_generated_on"] == "2026-08-17"
        assert product["report_window_days"] == 7
        assert product["revision"] == 1


def test_ownership_matrix_multiple_owned_and_owned_first(monkeypatch, tmp_path):
    first = _default_row("Синтетическая категория")
    second = dict(first)
    second[OZON_PRODUCTS_HEADERS[0]] = "A second product"
    second[OZON_PRODUCTS_HEADERS[1]] = "https://www.ozon.ru/product/100000002/"
    with _client(monkeypatch, tmp_path) as client:
        _post(client, build_ozon_products_workbook(rows=[first, second]))
        items = client.get("/api/products").json()["items"]
        assert client.patch(f"/api/products/{items[0]['id']}/ownership", json={"is_owned": True}).status_code == 200
        assert client.patch(f"/api/products/{items[1]['id']}/ownership", json={"is_owned": True}).status_code == 200
        assert client.get("/api/products").json()["readiness"] == "READY"
        assert client.patch(f"/api/products/{items[0]['id']}/ownership", json={"is_owned": False}).status_code == 200
        reordered = client.get("/api/products").json()["items"]
        assert reordered[0]["is_owned"] is True
        assert client.patch(f"/api/products/{items[0]['id']}/ownership").status_code == 422
        assert client.patch(f"/api/products/{items[0]['id']}/ownership", json={"is_owned": 1}).status_code == 422


def test_testclient_lifespan_recovers_before_serving_static_and_api(monkeypatch, tmp_path):
    db_path = tmp_path / "scoz.db"
    initialize_database(db_path)
    monkeypatch.setenv("SCOZ_DB_PATH", str(db_path))
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    imports = tmp_path / "imports"; imports.mkdir()
    interrupted = imports / ".upload-interrupted.part"; interrupted.write_bytes(b"x")
    with transaction(db_path) as conn:
        batch = LineageRepository(conn).create_import_batch(source="ozon", import_kind="ozon_products_xlsx")
    with TestClient(main.app) as client:
        with transaction(db_path) as conn:
            assert LineageRepository(conn).get_import_batch(batch.id).status is ImportStatus.FAILED
        assert not interrupted.exists()
        assert client.get("/api/health").status_code == 200
        assert client.get("/").status_code == 200
        assert client.get("/assets/js/app.js").status_code == 200
