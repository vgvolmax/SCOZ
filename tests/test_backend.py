import re
from pathlib import Path

from fastapi.testclient import TestClient

from backend.config import FRONTEND_DIST, VERSION
from backend.main import app

client = TestClient(app)


def test_health_identifies_current_scoz():
    assert client.get("/api/health").json() == {"status": "ok", "app": "SCOZ", "version": VERSION}


def test_root_serves_committed_frontend():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert '<div id="root"></div>' in response.text


def test_referenced_asset_is_served():
    html = (FRONTEND_DIST / "index.html").read_text(encoding="utf-8")
    path = re.search(r'["\'](/assets/[^"\']+)', html).group(1)
    assert client.get(path).status_code == 200


def test_unknown_paths_are_404():
    assert client.get("/api/not-real").status_code == 404
    assert client.get("/not-a-route").status_code == 404
