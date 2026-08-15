from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(name): return (ROOT / name).read_text(encoding="utf-8")

def test_version_and_requirements():
    assert read("VERSION.txt") == "0.1.0\n"
    assert read("requirements.txt").splitlines() == ["fastapi==0.139.2", "uvicorn==0.51.0"]
    assert "pytest" in read("requirements-dev.txt") and "pytest" not in read("requirements.txt")

def test_generated_state_ignored():
    ignored = read(".gitignore")
    for value in ["runtime/", "data/", ".venv/", "frontend/node_modules/", "*.enc.json"]: assert value in ignored
    assert "frontend/dist" not in ignored

def test_bootstrap_sources_and_validation():
    batch = read("start.bat")
    for value in ["https://www.python.org/ftp/python/3.13.14/python-3.13.14-embed-amd64.zip", "https://bootstrap.pypa.io/get-pip.py", ".part", "Entries.Count", "10000000", "python313.zip", "Lib\\site-packages", "import site", "m.version('fastapi') == '0.139.2'", "m.version('uvicorn') == '0.51.0'", 'import fastapi,uvicorn']:
        assert value in batch

def test_reuse_repair_rebuild_and_local_execution():
    batch = read("start.bat").lower()
    assert 'cd /d "%~dp0"' in batch
    assert '"runtime\\python.exe" -m pip install -r "requirements.txt"' in batch
    assert 'rmdir /s /q "runtime"' in batch and 'rmdir /s /q "data"' not in batch
    assert '"runtime\\python.exe" "launcher.py"' in batch
    assert not any(term in batch for term in ["npm ", "node_modules", "vite build", "--no-deps", "--only-binary", "runtime.__staging"])
