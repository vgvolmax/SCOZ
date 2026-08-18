from fastapi.testclient import TestClient

import backend.main as main
from backend.persistence.connection import transaction
from backend.persistence.database import initialize_database
from tests.xlsx_factory import build_ozon_search_visibility_workbook


def _client(monkeypatch, tmp_path):
    db_path = tmp_path / "scoz.db"
    initialize_database(db_path)
    monkeypatch.setenv("SCOZ_DB_PATH", str(db_path))
    monkeypatch.setattr(main, "DATA_DIR", tmp_path)
    return TestClient(main.app)


def _post(client, payload, filename="visibility.xlsx"):
    return client.post(
        "/api/imports/ozon-search-visibility",
        files={"file": (filename, payload, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )


def test_search_visibility_success_and_unified_history_do_not_pollute_products(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path) as client:
        response = _post(client, build_ozon_search_visibility_workbook())
        products = client.get("/api/products").json()
        history = client.get("/api/imports").json()
    assert response.status_code == 200
    assert response.json()["report_type"] == "OZON_SEARCH_VISIBILITY"
    assert products["items"] == [] and products["total"] == 0
    assert history["total"] == 1
    assert history["items"][0]["report_type"] == "OZON_SEARCH_VISIBILITY"


def test_search_visibility_transport_and_validation_errors_are_exact(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path) as client:
        media = client.post(
            "/api/imports/ozon-search-visibility", content=b"x",
            headers={"content-type": "application/octet-stream"},
        )
        missing = client.post(
            "/api/imports/ozon-search-visibility",
            files={"wrong": ("x.xlsx", b"x")},
        )
        unreadable = _post(client, b"uploaded-secret")
    assert media.status_code == 415
    assert media.json() == {"error": {"code": "UNSUPPORTED_UPLOAD_MEDIA_TYPE", "message": "Выберите XLSX-файл."}, "result": None}
    assert missing.status_code == 422
    assert unreadable.status_code == 422
    assert unreadable.json()["error"] == {"code": "UNSUPPORTED_WORKBOOK", "message": "Не удалось прочитать XLSX-файл."}
    assert b"uploaded-secret" not in unreadable.content


def test_search_visibility_import_persists_observations(monkeypatch, tmp_path):
    with _client(monkeypatch, tmp_path) as client:
        assert _post(client, build_ozon_search_visibility_workbook()).status_code == 200
    with transaction(tmp_path / "scoz.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM search_visibility_snapshots").fetchone()[0] == 1
