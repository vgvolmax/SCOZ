import json
from unittest.mock import Mock, patch

import launcher

def test_exact_health_identity():
    assert launcher.is_current_scoz({"status":"ok", "app":"SCOZ", "version":"0.1.0"})
    assert not launcher.is_current_scoz({"status":"ok", "app":"other", "version":"0.1.0"})
    assert not launcher.is_current_scoz({"status":"ok", "app":"SCOZ", "version":"old"})

def test_status_is_atomic(tmp_path):
    with patch.multiple(launcher, DATA_DIR=tmp_path, STATUS_FILE=tmp_path/"startup_status.json"), patch.object(launcher.os, "replace", wraps=launcher.os.replace) as replace:
        launcher.write_status("ready", "ok", state="ready")
        replace.assert_called_once_with(tmp_path/"startup_status.json.tmp", tmp_path/"startup_status.json")
        assert json.loads((tmp_path/"startup_status.json").read_text())["stage"] == "ready"

def test_already_running_does_not_start_duplicate():
    with patch.object(launcher, "configure_logging"), patch.object(launcher, "preflight"), patch.object(launcher, "probe_health", return_value=launcher.EXPECTED_HEALTH), patch.object(launcher, "start_wrapper") as start, patch.object(launcher, "write_status"), patch.object(launcher, "open_browser"):
        assert launcher.launch() == 0
        start.assert_not_called()

def test_foreign_port_fails_without_start_or_browser():
    with patch.object(launcher, "configure_logging"), patch.object(launcher, "preflight"), patch.object(launcher, "probe_health", return_value=None), patch.object(launcher, "port_is_occupied", return_value=True), patch.object(launcher, "start_wrapper") as start, patch.object(launcher, "write_status"), patch.object(launcher, "open_browser") as browser:
        assert launcher.launch() == 1
        start.assert_not_called(); browser.assert_not_called()

def test_browser_only_after_health_and_can_be_suppressed(monkeypatch):
    child = Mock(); child.poll.return_value = None
    with patch.object(launcher, "probe_health", side_effect=[None, launcher.EXPECTED_HEALTH]), patch.object(launcher.time, "sleep"):
        launcher.wait_until_ready(child, 1)
    monkeypatch.setenv("SCOZ_NO_BROWSER", "1")
    with patch.object(launcher.webbrowser, "open") as opened: launcher.open_browser(); opened.assert_not_called()

def test_wrapper_is_only_pid_writer():
    assert "server.pid" not in open("launcher.py", encoding="utf-8").read()
    wrapper = open("RUN_SERVER.cmd", encoding="utf-8").read()
    assert wrapper.count("server.pid") == 1
