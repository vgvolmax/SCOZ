import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_frozen_runtime_contract():
    assert (ROOT / "VERSION.txt").read_text().strip() == "0.1.0"
    manifest = json.loads((ROOT / "runtime_manifest.json").read_text())
    assert (manifest["schemaVersion"], manifest["pythonVersion"], manifest["architecture"]) == (1, "3.13.14", "amd64")
    assert manifest["python"] == {"url":"https://www.python.org/ftp/python/3.13.14/python-3.13.14-embed-amd64.zip", "sha256":"90b4e5b9898b72d744650524bff92377c367f44bd5fbd09e3148656c080ad907"}
    assert manifest["pipBootstrap"]["url"] == "https://bootstrap.pypa.io/get-pip.py"
    assert re.fullmatch(r"[0-9a-f]{64}", manifest["pipBootstrap"]["sha256"])


def test_lock_is_exact_and_windows_complete():
    packages = [x for x in (ROOT / "requirements.lock.txt").read_text().splitlines() if x and not x.startswith("#")]
    assert all(re.fullmatch(r"[A-Za-z0-9_.-]+==[^=<>~!\s]+", x) for x in packages)
    names = {x.split("==")[0].lower().replace("_", "-") for x in packages}
    assert {"fastapi", "uvicorn", "colorama"} <= names


def test_bootstrap_integrity_and_rollback_contract():
    text = (ROOT / "scripts/bootstrap.ps1").read_text()
    assert "Get-FileHash" in text and "Expand-Archive" in text
    assert text.index("Get-VerifiedFile $Manifest.python.url") < text.index("Expand-Archive")
    assert text.count("--only-binary=:all: --no-deps") >= 1
    assert "runtime.__staging.$PID" in text and "runtime.__old.$PID" in text
    assert "Move-Item -LiteralPath $old -Destination $Runtime" in text


def test_thin_bat_and_generated_state_ignore():
    bat = (ROOT / "start.bat").read_text()
    assert 'cd /d "%~dp0"' in bat and "scripts\\bootstrap.ps1" in bat
    assert not re.search(r"pip install|Invoke-WebRequest|curl", bat, re.I)
    ignore = (ROOT / ".gitignore").read_text()
    for entry in ("runtime/", "data/", ".venv/", ".lock-venv/", "frontend/node_modules/", "*.enc.json"):
        assert entry in ignore
    assert "frontend/dist/" not in ignore
