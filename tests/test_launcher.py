import io
import json

import pytest
import launcher


class Response(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *_): return None


@pytest.mark.parametrize("payload,expected", [
    ({"status":"ok","app":"SCOZ","version":launcher.VERSION}, True),
    ({"status":"ok","app":"other","version":launcher.VERSION}, False),
    ({"status":"ok","app":"SCOZ","version":"0.0.1"}, False)])
def test_health_requires_scoz_identity_and_current_version(monkeypatch, payload, expected):
    monkeypatch.setattr(launcher.urllib.request, "urlopen", lambda *a, **k: Response(json.dumps(payload).encode()))
    assert launcher.probe_health() is expected


def test_status_write_replaces_file_atomically(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher, "DATA_DIR", tmp_path)
    monkeypatch.setattr(launcher, "STATUS_PATH", tmp_path / "startup_status.json")
    launcher.write_startup_status("preflight", "one")
    launcher.write_startup_status("ready", "two")
    assert json.loads(launcher.STATUS_PATH.read_text())["message"] == "two"
    assert not (tmp_path / "startup_status.json.tmp").exists()


def test_invalid_status_stage_is_rejected():
    with pytest.raises(ValueError): launcher.write_startup_status("invented", "no")


def test_no_browser_env_suppresses_open(monkeypatch):
    called=[]; monkeypatch.setenv("SCOZ_NO_BROWSER", "1")
    monkeypatch.setattr(launcher.webbrowser, "open", lambda url: called.append(url))
    launcher.open_browser(); assert called == []


def test_browser_open_happens_only_after_health(monkeypatch, tmp_path):
    events=[]
    monkeypatch.setattr(launcher, "DATA_DIR", tmp_path); monkeypatch.setattr(launcher, "STATUS_PATH", tmp_path/"s.json")
    monkeypatch.setattr(launcher, "LOG_PATH", tmp_path/"l.log")
    monkeypatch.setattr(launcher, "probe_health", lambda: False)
    monkeypatch.setattr(launcher, "port_is_occupied", lambda: True)
    monkeypatch.setattr(launcher, "open_browser", lambda: events.append("browser"))
    assert launcher.run_start() == 1 and events == []


def test_start_server_writes_pid(tmp_path, monkeypatch):
    class P: pid=42
    monkeypatch.setattr(launcher, "DATA_DIR", tmp_path); monkeypatch.setattr(launcher, "PID_PATH", tmp_path/"server.pid")
    monkeypatch.setattr(launcher, "SERVER_LOG_PATH", tmp_path/"server.log")
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *a, **k: P())
    launcher.start_server_process(); assert launcher.PID_PATH.read_text() == "42"
