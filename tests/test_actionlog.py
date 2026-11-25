import json

import pytest
from fastapi.testclient import TestClient

from agent import actionlog as A
from app import app

c = TestClient(app)


@pytest.fixture
def log(tmp_path):
    return tmp_path / "action_log.jsonl"


def test_entries_are_numbered_and_chained(log):
    a = A.append("stock", "return requested", "Pradip Ghosh", "K2300101")
    b = A.append("supply", "move approved", "Kavita Rao", "S02 PFL1001")
    assert (a["seq"], b["seq"]) == (1, 2) and b["prev"] == a["hash"] and a["prev"] == A.GENESIS
    assert A.verify() == dict(ok=True, entries=2, broken_at=None)


def test_a_changed_or_removed_line_is_detected(log):
    for i in range(3):
        A.append("stock", "no action", "Subhajit", f"b{i}")
    lines = log.read_text().splitlines()
    edited = json.loads(lines[1]); edited["by"] = "someone else"
    log.write_text("\n".join([lines[0], json.dumps(edited), lines[2]]) + "\n")
    assert A.verify()["ok"] is False and A.verify()["broken_at"] == 2
    log.write_text("\n".join([lines[0], lines[2]]) + "\n")      # a removed line
    assert A.verify()["ok"] is False


def test_only_allowed_steps_and_a_name_are_accepted():
    with pytest.raises(ValueError):
        A.append("stock", "move approved", "X")      # a supply step on the stock desk
    with pytest.raises(ValueError):
        A.append("stock", "no action", "  ")


def test_api_records_and_lists_newest_first(log):
    r = c.post("/api/action", json=dict(desk="schemes", step="RSM warned", by="Arjun Sethi", ref="STK0140 PFL1105"))
    assert r.status_code == 200 and r.json()["entry"]["seq"] == 1
    c.post("/api/action", json=dict(desk="supply", step="move declined", by="Kavita Rao", note="no transport"))
    d = c.get("/api/actions").json()
    assert [e["seq"] for e in d["entries"]] == [2, 1] and d["chain"]["ok"] and "supply" in d["steps"]
    assert [e["desk"] for e in c.get("/api/actions?desk=schemes").json()["entries"]] == ["schemes"]
    assert c.post("/api/action", json=dict(desk="stock", step="bogus", by="X")).status_code == 422


def test_a_claim_decision_is_written_to_the_log_with_its_reason():
    r = c.post("/api/decision", json=dict(claim_ref="CLM-2608-01758", recommended="REJECT", action="override", reason="Area Manager approval seen", reviewer="Neha Bansal"))
    assert r.json()["recorded"] is True
    e = c.get("/api/actions").json()["entries"][0]
    assert e["step"] == "decision overridden" and "Area Manager approval seen" in e["note"] and e["by"] == "Neha Bansal"
    assert c.post("/api/decision", json=dict(claim_ref="X", recommended="REJECT", action="override")).status_code == 422


def test_unwritable_log_does_not_lose_the_answer(monkeypatch, tmp_path):
    monkeypatch.setenv("ACTION_LOG", str(tmp_path / "no_such" / "x" / "log.jsonl"))
    monkeypatch.setattr(A.Path, "mkdir", lambda *a, **k: (_ for _ in ()).throw(PermissionError()))
    assert c.post("/api/decision", json=dict(claim_ref="X", recommended="APPROVE", action="accept")).json()["recorded"] is False
