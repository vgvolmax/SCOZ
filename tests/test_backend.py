from pathlib import Path

from fastapi.testclient import TestClient

from backend import config
from backend.main import app


client = TestClient(app)


def test_health_contract_and_configuration():
    assert config.HOST == "127.0.0.1"
    assert config.PORT == 17842
    assert config.VERSION == Path("VERSION.txt").read_text(encoding="utf-8").strip()
    assert client.get("/api/health").json() == {"status": "ok", "app": "SCOZ", "version": "0.1.0"}


def test_static_files_and_no_fallback():
    assert client.get("/").status_code == 200
    assert "SCOZ" in client.get("/").text
    assert client.get("/assets/css/app.css").status_code == 200
    assert client.get("/assets/missing.css").status_code == 404
    assert client.get("/api/missing").status_code == 404
    assert client.get("/unknown").status_code == 404


def test_backend_does_not_create_database(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client.get("/api/health")
    assert not list(tmp_path.rglob("*.db"))
    assert not list(tmp_path.rglob("*.sqlite*"))
