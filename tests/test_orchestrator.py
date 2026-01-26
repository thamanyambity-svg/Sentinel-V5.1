import os
from bot.workflow.orchestrator import run_orchestrator

def test_kill_switch_blocked(monkeypatch):
    monkeypatch.setenv("KILL_SWITCH", "1")
    res = run_orchestrator()
    assert res["status"] == "BLOCKED"
    assert res["reason"] == "KILL_SWITCH_ACTIVE"

def test_health_not_ok(monkeypatch):
    monkeypatch.delenv("KILL_SWITCH", raising=False)
    monkeypatch.setenv("FORCE_HEALTH_KO", "1")
    res = run_orchestrator()
    assert res["status"] == "BLOCKED"
    assert res["reason"] == "HEALTH_NOT_OK"

def test_shadow_trade(monkeypatch):
    monkeypatch.delenv("FORCE_HEALTH_KO", raising=False)
    monkeypatch.setenv("SHADOW_MODE", "1")
    res = run_orchestrator()
    assert res["status"] in ("OK", "SHADOW", "NO_TRADE")

def test_nominal_trade(monkeypatch):
    monkeypatch.delenv("SHADOW_MODE", raising=False)
    res = run_orchestrator()
    assert "status" in res
