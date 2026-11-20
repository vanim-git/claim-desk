from fastapi.testclient import TestClient

import agent.graph as g
from app import app

client = TestClient(app)


def test_health_without_key(monkeypatch):
    monkeypatch.setattr("app.llm_available", lambda: False)
    assert client.get("/api/health").json() == {"ok": True, "model_key_set": False}


def test_claim_by_number(monkeypatch):
    monkeypatch.setattr(g, "llm_available", lambda: False)
    r = client.post("/api/claim", json={"claim_no": "CLM-2603-02697"})
    assert r.status_code == 200 and r.json()["results"][0]["outcome"] == "REJECT"


def test_claim_needs_some_input():
    assert client.post("/api/claim", json={}).status_code == 422


def test_override_needs_reason():
    body = dict(claim_ref="X", recommended="REJECT", action="override")
    assert client.post("/api/decision", json=body).status_code == 422
    assert client.post("/api/decision", json=body | {"reason": "Area Manager approved"}).json()["recorded"] is True


def test_index_served():
    assert client.get("/").status_code == 200
