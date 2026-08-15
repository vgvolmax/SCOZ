import io
import json

import pytest

import launcher


class Response(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *_): return None


@pytest.mark.parametrize("payload,expected", [
    ({"status":"ok","app":"SCOZ","version":launcher.VERSION}, True),
    ({"status":"ok","app":"Other","version":launcher.VERSION}, False),
    ({"status":"ok","app":"SCOZ","version":"0.0.1"}, False),
])
def test_health_requires_exact_identity(monkeypatch, payload, expected):
    monkeypatch.setattr(launcher.urllib.request, "urlopen", lambda *a, **k: Response(json.dumps(payload).encode()))
    assert launcher.probe_health() is expected


def test_status_is_atomic_and_stage_validated(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "DATA_DIR", tmp_path)
    monkeypatch.setattr(launcher, "STATUS_FILE", tmp_path / "startup_status.json")
    launcher.write_startup_status("ready", "ok")
    assert json.loads(launcher.STATUS_FILE.read_text())["stage"] == "ready"
    assert not (tmp_path / "startup_status.json.tmp").exists()
    with pytest.raises(ValueError): launcher.write_startup_status("invented", "no")


def test_browser_suppression(monkeypatch):
    called = []
    monkeypatch.setenv("SCOZ_NO_BROWSER", "1")
    monkeypatch.setattr(launcher.webbrowser, "open", called.append)
    launcher.open_browser()
    assert called == []


def test_foreign_port_fails_before_server_or_browser(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "DATA_DIR", tmp_path)
    monkeypatch.setattr(launcher, "STATUS_FILE", tmp_path / "status")
    monkeypatch.setattr(launcher, "LOG_FILE", tmp_path / "log")
    monkeypatch.setattr(launcher, "probe_health", lambda: False)
    monkeypatch.setattr(launcher, "port_is_occupied", lambda: True)
    monkeypatch.setattr(launcher, "start_server_process", lambda: pytest.fail("server started"))
    monkeypatch.setattr(launcher, "open_browser", lambda: pytest.fail("browser opened"))
    assert launcher.run_start() == 1


def test_browser_is_after_health(monkeypatch, tmp_path):
    events = []
    process = type("Process", (), {"pid": 7})()
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("ok")
    monkeypatch.setattr(launcher, "FRONTEND_DIST", dist)
    monkeypatch.setattr(launcher, "DATA_DIR", tmp_path)
    monkeypatch.setattr(launcher, "STATUS_FILE", tmp_path / "status")
    monkeypatch.setattr(launcher, "LOG_FILE", tmp_path / "log")
    monkeypatch.setattr(launcher, "probe_health", lambda: False)
    monkeypatch.setattr(launcher, "port_is_occupied", lambda: False)
    monkeypatch.setattr(launcher, "start_server_process", lambda: (events.append("start"), process)[1])
    monkeypatch.setattr(launcher, "wait_until_healthy", lambda **k: (events.append("healthy"), True)[1])
    monkeypatch.setattr(launcher, "open_browser", lambda: events.append("browser"))
    assert launcher.run_start() == 0
    assert events == ["start", "healthy", "browser"]


def test_start_process_writes_pid(tmp_path, monkeypatch):
    class Process: pid = 321
    monkeypatch.setattr(launcher, "DATA_DIR", tmp_path)
    monkeypatch.setattr(launcher, "PID_FILE", tmp_path / "server.pid")
    monkeypatch.setattr(launcher, "SERVER_LOG", tmp_path / "server.log")
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *a, **k: Process())
    launcher.start_server_process()
    assert launcher.PID_FILE.read_text().strip() == "321"
