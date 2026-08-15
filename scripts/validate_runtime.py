from __future__ import annotations

import importlib
import importlib.metadata
import json
import platform
import re
import sys
from pathlib import Path


def validate(root: Path) -> None:
    manifest = json.loads((root / "runtime_manifest.json").read_text(encoding="utf-8"))
    if platform.python_version() != manifest["pythonVersion"]:
        raise RuntimeError("Python version mismatch")
    machine = platform.machine().lower()
    if sys.platform == "win32" and machine not in {"amd64", "x86_64"}:
        raise RuntimeError("Runtime architecture mismatch")
    for raw in (root / "requirements.lock.txt").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^=<>~!\s]+)", line)
        if not match:
            raise RuntimeError(f"Invalid lock entry: {line}")
        name, expected = match.groups()
        if importlib.metadata.version(name) != expected:
            raise RuntimeError(f"Package mismatch: {name}")
    importlib.import_module("fastapi")
    importlib.import_module("uvicorn")


if __name__ == "__main__":
    try:
        validate(Path(sys.argv[1]).resolve())
    except Exception as error:
        print(f"Runtime validation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
