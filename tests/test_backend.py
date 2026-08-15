from pathlib import Path

from fastapi.testclient import TestClient

from backend import config
from backend.main import app

client = TestClient(app)

def test_fixed_configuration_and_version():
    assert (config.APP_NAME, config.HOST, config.PORT) == ("SCOZ", "127.0.0.1", 17842)
    assert config.VERSION == Path("VERSION.txt").read_text(encoding="utf-8").strip() == "0.1.0"

def test_exact_health():
    assert client.get("/api/health").json() == {"status": "ok", "app": "SCOZ", "version": "0.1.0"}

def test_static_routes_and_no_fallback():
    assert client.get("/").status_code == 200
    assets = list((config.FRONTEND_DIST / "assets").glob("*"))
    assert assets and client.get(f"/assets/{assets[0].name}").status_code == 200
    assert client.get("/assets/missing.js").status_code == 404
    assert client.get("/api/missing").status_code == 404
    assert client.get("/missing").status_code == 404

def test_backend_does_not_create_database():
    assert not list(config.ROOT.glob("**/*.db"))
