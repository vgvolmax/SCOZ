from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from backend.config import APP_NAME, FRONTEND_DIST, HOST, PORT, ROOT, VERSION

DATA_DIR = ROOT / "data"
STATUS_FILE = DATA_DIR / "startup_status.json"
LOG_FILE = DATA_DIR / "launcher.log"
PID_FILE = DATA_DIR / "server.pid"
SERVER_LOG = DATA_DIR / "server_console.log"
URL = f"http://{HOST}:{PORT}"
HEALTH_URL = f"{URL}/api/health"
ALLOWED_STAGES = {"preflight", "runtime_setup", "database_backup", "migration", "server_start", "ready", "failed"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def log(message: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as stream:
        stream.write(f"{utc_now()} {message}\n")


def write_startup_status(stage: str, message: str) -> None:
    if stage not in ALLOWED_STAGES:
        raise ValueError(f"Unknown startup stage: {stage}")
    now = utc_now()
    payload = {"stage": stage, "message": message, "startedAt": os.environ.get("SCOZ_STARTUP_STARTED_AT", now), "updatedAt": now}
    atomic_write(STATUS_FILE, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def probe_health(timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=timeout) as response:
            payload = json.load(response)
        return payload.get("status") == "ok" and payload.get("app") == APP_NAME and payload.get("version") == VERSION
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def port_is_occupied() -> bool:
    with socket.socket() as probe:
        probe.settimeout(0.5)
        return probe.connect_ex((HOST, PORT)) == 0


def open_browser() -> None:
    if os.environ.get("SCOZ_NO_BROWSER") != "1":
        webbrowser.open(URL)


def start_server_process() -> subprocess.Popen[bytes]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    output = SERVER_LOG.open("ab")
    kwargs: dict[str, object] = {"cwd": ROOT, "stdout": output, "stderr": subprocess.STDOUT}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    process = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--host", HOST, "--port", str(PORT), "--no-access-log"], **kwargs)
    output.close()
    atomic_write(PID_FILE, f"{process.pid}\n")
    return process


def wait_until_healthy(timeout_seconds: float = 30.0, interval_seconds: float = 0.25, process: subprocess.Popen[bytes] | None = None) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if probe_health():
            return True
        if process is not None and process.poll() is not None:
            return False
        time.sleep(interval_seconds)
    return False


def run_start() -> int:
    try:
        write_startup_status("preflight", "Проверяем готовность SCOZ")
        if not ROOT.is_dir() or not (FRONTEND_DIST / "index.html").is_file():
            raise RuntimeError("Не найдены файлы приложения")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if probe_health():
            write_startup_status("ready", "SCOZ уже запущен")
            log("Current SCOZ instance is already running")
            open_browser()
            return 0
        if port_is_occupied():
            raise RuntimeError(f"Порт {PORT} занят другим приложением или другой версией SCOZ")
        write_startup_status("server_start", "Запускаем SCOZ")
        process = start_server_process()
        if not wait_until_healthy(process=process):
            raise RuntimeError("Сервер SCOZ не прошёл проверку готовности")
        write_startup_status("ready", "SCOZ готов к работе")
        log(f"SCOZ ready at {URL}; server PID {process.pid}")
        open_browser()
        return 0
    except Exception as error:
        log(f"Startup failed: {error}")
        write_startup_status("failed", "SCOZ не удалось запустить")
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", action="store_true")
    args = parser.parse_args()
    raise SystemExit(run_start() if args.start else parser.error("use --start"))
