from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_inputs():
    assert (ROOT / "VERSION.txt").read_text(
        encoding="utf-8"
    ).strip() == "0.1.0"
    assert (ROOT / "requirements.txt").read_text().splitlines() == ["fastapi==0.139.2", "uvicorn==0.51.0"]
    assert "pytest" in (ROOT / "requirements-dev.txt").read_text()


def test_bootstrap_contract():
    text = (ROOT / "start.bat").read_text(encoding="utf-8")
    required = [
        'cd /d "%~dp0"', "python-3.13.14-embed-amd64.zip", "https://www.python.org/ftp/python/3.13.14/",
        "https://bootstrap.pypa.io/get-pip.py", ".part", "Entries.Count", "5000000", "100000",
        "python313.zip", "Lib\\site-packages", "import site", '-m pip install -r "requirements.txt"',
        "(3,13,14)", "AMD64", "fastapi", "0.139.2", "uvicorn", "0.51.0", 'rmdir /s /q "runtime"',
        '"runtime\\python.exe" "launcher.py"',
    ]
    for value in required:
        assert value in text
    lowered = text.lower()
    assert "npm " not in lowered and "node " not in lowered and "frontend build" not in lowered
    assert 'rmdir /s /q "data"' not in lowered


def test_ignored_generated_and_sensitive_state():
    ignore = (ROOT / ".gitignore").read_text()
    for item in ("runtime/", "data/", ".venv/", "__pycache__/", "*.enc.json", "*credentials*.json"):
        assert item in ignore
    wrapper = (ROOT / "RUN_SERVER.cmd").read_text()
    assert '"%~dp0"' in wrapper
    assert "server.pid" in wrapper and "server_console.log" in wrapper
