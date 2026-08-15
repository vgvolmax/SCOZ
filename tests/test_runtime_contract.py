import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_version_is_pr1_version():
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "0.1.0"


def test_runtime_manifest_is_fully_pinned():
    manifest = json.loads((ROOT / "runtime_manifest.json").read_text(encoding="utf-8"))
    assert manifest["schemaVersion"] == 1
    assert manifest["pythonVersion"] == "3.13.14"
    assert manifest["architecture"] == "amd64"
    assert manifest["python"]["url"] == "https://www.python.org/ftp/python/3.13.14/python-3.13.14-embed-amd64.zip"
    assert manifest["python"]["sha256"] == "90b4e5b9898b72d744650524bff92377c367f44bd5fbd09e3148656c080ad907"
    assert manifest["pipBootstrap"]["url"] == "https://bootstrap.pypa.io/get-pip.py"
    assert re.fullmatch(r"[0-9a-f]{64}", manifest["pipBootstrap"]["sha256"])


def test_runtime_lock_is_exactly_pinned():
    packages = [line.strip() for line in (ROOT / "requirements.lock.txt").read_text().splitlines()
                if line.strip() and not line.startswith("#")]
    assert packages
    assert all(re.fullmatch(r"[A-Za-z0-9_.-]+==[^=<>~!\s]+", line) for line in packages)
    names = {line.split("==", 1)[0].lower().replace("_", "-") for line in packages}
    assert {"fastapi", "uvicorn"} <= names


def test_user_state_is_ignored_but_frontend_dist_is_not():
    text = (ROOT / ".gitignore").read_text()
    for required in ("runtime/", "data/", ".venv/", "frontend/node_modules/", "*.enc.json"):
        assert required in text
    assert "frontend/dist/" not in text


def test_thin_start_and_verified_bootstrap_contracts():
    batch = (ROOT / "start.bat").read_text(encoding="utf-8").lower()
    assert 'cd /d "%~dp0"' in batch and "scripts\\bootstrap.ps1" in batch
    assert all(term not in batch for term in ("pip install", "invoke-webrequest", "curl"))
    bootstrap = (ROOT / "scripts/bootstrap.ps1").read_text(encoding="utf-8").lower()
    assert "runtime_manifest.json" in bootstrap and "requirements.lock.txt" in bootstrap
    assert bootstrap.index("get-filehash") < bootstrap.index("expand-archive")
    assert "runtime.__staging" in bootstrap and "launcher.py') --start" in bootstrap
    install_prefix = "pip install --disable-pip-version-check --only-binary=:all: --no-deps -r"
    assert bootstrap.count(install_prefix) == 2
