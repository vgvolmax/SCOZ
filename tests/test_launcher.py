import json
from pathlib import Path
from unittest.mock import Mock

import pytest

import launcher


def configure_data(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "DATA_DIR", tmp_path)


def test_atomic_status(monkeypatch, tmp_path):
    configure_data(monkeypatch, tmp_path)
    replace = Mock(wraps=launcher.os.replace)
    monkeypatch.setattr(launcher.os, "replace", replace)
    launcher.write_status("ready", "ok", ok=True)
    replace.assert_called_once_with(tmp_path / "startup_status.json.tmp", tmp_path / "startup_status.json")
    assert json.loads((tmp_path / "startup_status.json").read_text())["stage"] == "ready"
    assert not (tmp_path / "startup_status.json.tmp").exists()


def test_exact_health_identity():
    assert launcher.expected_health({"status": "ok", "app": "SCOZ", "version": "0.1.0"})
    assert not launcher.expected_health({"status": "ok", "app": "other", "version": "0.1.0"})
    assert not launcher.expected_health({"status": "ok", "app": "SCOZ", "version": "old"})


def test_already_running_does_not_start_or_change_pid(monkeypatch, tmp_path):
    configure_data(monkeypatch, tmp_path)
    pid = tmp_path / "server.pid"; pid.write_text("123")
    monkeypatch.setattr(launcher, "preflight", lambda: None)
    monkeypatch.setattr(launcher, "fetch_health", lambda: {"status": "ok", "app": "SCOZ", "version": "0.1.0"})
    start = Mock(); browser = Mock()
    monkeypatch.setattr(launcher, "start_wrapper", start); monkeypatch.setattr(launcher, "open_browser", browser)
    assert launcher.launch() == 0
    start.assert_not_called(); browser.assert_called_once(); assert pid.read_text() == "123"


def test_foreign_port_fails_without_browser(monkeypatch, tmp_path):
    configure_data(monkeypatch, tmp_path)
    monkeypatch.setattr(launcher, "preflight", lambda: None)
    monkeypatch.setattr(launcher, "fetch_health", lambda: None)
    monkeypatch.setattr(launcher, "port_is_open", lambda: True)
    browser = Mock(); start = Mock()
    monkeypatch.setattr(launcher, "open_browser", browser); monkeypatch.setattr(launcher, "start_wrapper", start)
    assert launcher.launch() == 1
    browser.assert_not_called(); start.assert_not_called()


def test_browser_only_after_health(monkeypatch, tmp_path):
    configure_data(monkeypatch, tmp_path)
    monkeypatch.setattr(launcher, "preflight", lambda: None)
    monkeypatch.setattr(launcher, "fetch_health", lambda: None)
    monkeypatch.setattr(launcher, "port_is_open", lambda: False)
    process = Mock(); monkeypatch.setattr(launcher, "start_wrapper", lambda: process)
    events = []
    monkeypatch.setattr(launcher, "wait_until_ready", lambda p: events.append("health") or True)
    monkeypatch.setattr(launcher, "open_browser", lambda: events.append("browser"))
    assert launcher.launch() == 0 and events == ["health", "browser"]


def test_no_browser_switch(monkeypatch):
    monkeypatch.setenv("SCOZ_NO_BROWSER", "1")
    opened = Mock(); monkeypatch.setattr(launcher.webbrowser, "open", opened)
    launcher.open_browser(); opened.assert_not_called()


def test_child_failure_and_timeout():
    dead = Mock(); dead.poll.return_value = 7; dead.returncode = 7
    with pytest.raises(RuntimeError, match="код 7"):
        launcher.wait_until_ready(dead, timeout=.01)
    alive = Mock(); alive.poll.return_value = None
    with pytest.raises(RuntimeError, match="вовремя"):
        launcher.wait_until_ready(alive, timeout=0)


def test_wrapper_is_sole_pid_writer():
    wrapper = Path("RUN_SERVER.cmd").read_text(encoding="utf-8")
    source = Path("launcher.py").read_text(encoding="utf-8")
    assert "server.pid" in wrapper and "server.pid" not in source
