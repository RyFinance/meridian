"""Setup page data and the desk's kill-switch buttons."""
import pytest
from fastapi.testclient import TestClient

import bot.kill_switch as ks
from live_backtest.dashboard import backend


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(ks, "KILL_SWITCH_FILE", tmp_path / "KILL_SWITCH")
    monkeypatch.setattr(ks, "STATE_DIR", tmp_path)
    return TestClient(backend.app)


def test_setup_lists_checks_settings_and_live_steps(client):
    body = client.get("/api/setup").json()
    assert {c["id"] for c in body["checks"]} >= {"python", "model", "env", "prices", "cycle", "schedule", "broker", "live"}
    names = {r["name"] for r in body["settings"]}
    assert {"MERIDIAN_ALLOW_LIVE", "MERIDIAN_LIVE_MAX_ORDER_USD"} <= names
    assert all("secret" not in r["now"].lower() for r in body["settings"])  # never echoes key values
    brokers = {b["id"] for b in body["live_setup"]}
    assert "alpaca" in brokers and "questrade" not in brokers  # no live orders on Questrade
    assert body["limits"]["max_drawdown_pct"] == 0.20


def test_kill_switch_engages_freely_but_clears_only_with_resume(client):
    assert client.post("/api/kill/engage", json={}).json()["engaged"] is True
    assert client.post("/api/kill/clear", json={"confirm": "yes"}).status_code == 400
    assert ks.is_kill_switch_engaged()
    assert client.post("/api/kill/clear", json={"confirm": "resume"}).json()["engaged"] is False
