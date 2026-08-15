"""Start the local SCOZ server and open its UI after strict health succeeds."""
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
STATUS_PATH = DATA_DIR / "startup_status.json"
LOG_PATH = DATA_DIR / "launcher.log"
SERVER_LOG_PATH = DATA_DIR / "server_console.log"
PID_PATH = DATA_DIR / "server.pid"
URL = f"http://{HOST}:{PORT}"
HEALTH_URL = f"{URL}/api/health"
ALLOWED_STAGES = {"preflight", "runtime_setup", "database_backup", "migration", "server_start", "ready", "failed"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(message: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as stream:
        stream.write(f"{_now()} {message}\n")


def write_startup_status(stage: str, message: str) -> None:
    if stage not in ALLOWED_STAGES:
        raise ValueError(f"Unknown startup stage: {stage}")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    now = _now()
    payload = {"stage": stage, "message": message,
               "startedAt": os.environ.get("SCOZ_STARTUP_STARTED_AT", now), "updatedAt": now}
    temporary = STATUS_PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, STATUS_PATH)


def probe_health(timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload.get("status") == "ok" and payload.get("app") == APP_NAME and payload.get("version") == VERSION
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def port_is_occupied() -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=.4):
            return True
    except OSError:
        return False


def open_browser() -> None:
    if os.environ.get("SCOZ_NO_BROWSER") != "1":
        webbrowser.open(URL)


def start_server_process() -> subprocess.Popen:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    stream = SERVER_LOG_PATH.open("ab")
    kwargs: dict[str, object] = {"cwd": ROOT, "stdout": stream, "stderr": subprocess.STDOUT}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    process = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--host", HOST,
                                "--port", str(PORT), "--no-access-log"], **kwargs)
    temporary = PID_PATH.with_suffix(".pid.tmp")
    temporary.write_text(str(process.pid), encoding="ascii")
    os.replace(temporary, PID_PATH)
    return process


def wait_until_healthy(timeout_seconds: float = 30.0, interval_seconds: float = .25,
                       process: subprocess.Popen | None = None) -> bool:
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
            raise RuntimeError("Файлы SCOZ неполны: не найден production UI")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if probe_health():
            write_startup_status("ready", "SCOZ уже запущен")
            log("Current SCOZ instance is already healthy")
            open_browser()
            return 0
        if port_is_occupied():
            raise RuntimeError(f"Порт {PORT} занят другим или устаревшим процессом")
        process = start_server_process()
        write_startup_status("server_start", "Запускаем SCOZ")
        if not wait_until_healthy(process=process):
            raise RuntimeError("SCOZ не прошёл проверку готовности")
        write_startup_status("ready", "SCOZ готов к работе")
        log(f"SCOZ {VERSION} is ready at {URL}")
        open_browser()
        return 0
    except Exception as error:
        message = str(error)
        log(f"Startup failed: {message}")
        write_startup_status("failed", message)
        return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", action="store_true")
    args = parser.parse_args()
    sys.exit(run_start() if args.start else parser.error("use --start"))
