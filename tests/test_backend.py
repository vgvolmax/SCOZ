import re
from pathlib import Path

from fastapi.testclient import TestClient

from backend.config import VERSION
from backend.main import app

ROOT = Path(__file__).resolve().parents[1]
client = TestClient(app)


def test_health_identifies_current_scoz():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "app": "SCOZ", "version": VERSION}


def test_root_and_generated_asset_are_served():
    response = client.get("/")
    assert response.status_code == 200
    assert '<div id="root"></div>' in response.text
    asset = re.search(r'(?:src|href)="(/assets/[^"]+)"', response.text)
    assert asset and client.get(asset.group(1)).status_code == 200


def test_unknown_paths_are_404():
    assert client.get("/api/not-real").status_code == 404
    assert client.get("/not-a-route").status_code == 404
