"""The whole graph on real data in data/, with no model key (rules read the emails)."""
import pytest

import agent.graph as g


@pytest.fixture(autouse=True)
def no_model(monkeypatch):
    monkeypatch.setattr(g, "llm_available", lambda: False)


def outcomes(req):
    return [r["outcome"] for r in g.run_claim(req)["results"]]


def test_injection_email_is_never_approved():
    r = g.run_claim({"email_id": "EML-017"})
    assert "injection_suspected" in r["flags"]
    assert all(x["outcome"] != "APPROVE" for x in r["results"])


def test_multi_line_email_gives_one_result_per_line():
    assert len(g.run_claim({"email_id": "EML-009"})["results"]) == 2


def test_repeat_line_in_one_email_rejected():
    assert "REJECT" in outcomes({"email_id": "EML-013"})


def test_already_logged_claims():
    assert outcomes({"email_id": "EML-019"}) == ["ALREADY_LOGGED"]


def test_status_query_and_forwarding():
    assert g.run_claim({"email_id": "EML-023"})["status_reply"]["found"] is True
    assert g.run_claim({"email_id": "EML-028"})["forward_to"]


def test_register_claims_follow_the_policy_decision():
    assert outcomes({"claim_no": "CLM-2603-02697"}) == ["REJECT"]  # quantity above supply: recommend reject, a person decides
    assert outcomes({"claim_no": "CLM-2608-01758"}) == ["REJECT"]


def test_unknown_claim_number_is_an_error_not_a_guess():
    r = g.run_claim({"claim_no": "CLM-0000-00000"})
    assert r["error"] and not r["results"]


def test_new_claim_missing_fields_goes_to_a_person():
    r = g.run_claim({"claim": {"stockist_code": "STK0140", "batch_no": "NOPE123", "qty": 5, "claim_type": "Expired"}})
    assert all(x["outcome"] != "APPROVE" for x in r["results"])


def test_audit_reproduces_the_373_claims():
    assert g.audit_credited()["claims"] == 373


def test_box_without_pack_size_goes_to_a_person(monkeypatch):
    monkeypatch.setattr(g, "regex_parse", lambda body, *a, **k: {"intent": "claim", "status_ref": None, "lines": [
        dict(batch_no="J2410392", qty=5, unit="boxes", per_box=None, stated_expiry=None, invoice_no=None)]})
    r = g.run_claim({"email_text": "x", "sender": "STK0126", "received": "2026-03-10"})
    assert "unit_unclear" in r["results"][0]["flags"] and r["results"][0]["outcome"] != "APPROVE"


def test_resent_rejected_claim_is_judged_on_the_original_date():
    from agent import data as D
    d = D.get()
    c = next(x for v in d.rejected.values() for x in v
             if not any(y["qty"] == x["qty"] for y in d.by_key.get((x["stockist"], x["batch"]), [])))
    r = g.run_claim({"claim": {"stockist_code": c["stockist"], "batch_no": c["batch"], "qty": c["qty"],
                                "claim_type": c["claim_type"], "claim_date": "2026-11-20", "invoice_ref": c["invoice_ref"]}})
    x = r["results"][0]
    assert x["outcome"] != "ALREADY_LOGGED" and any("resubmission of " + c["claim_no"] in n for n in x["notes"])
