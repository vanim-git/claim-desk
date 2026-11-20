"""Regression set: the 30 sample emails, outcome per line, rules only (no model). Regenerate only if the policy defaults change."""
import pytest

import agent.graph as g

EXPECTED = {
    "EML-001": ["APPROVE"], "EML-002": ["APPROVE"] * 3, "EML-003": ["NEEDS_PERSON"] * 2, "EML-004": ["APPROVE"],
    "EML-005": ["NEEDS_PERSON"], "EML-006": ["NEEDS_PERSON"], "EML-007": ["NEEDS_PERSON"], "EML-008": ["NEEDS_PERSON"],
    "EML-009": ["APPROVE", "REJECT"], "EML-010": ["REJECT"], "EML-011": ["NEEDS_PERSON"], "EML-012": ["NEEDS_PERSON"],
    "EML-013": ["APPROVE", "REJECT"], "EML-014": ["REJECT"], "EML-015": ["REJECT"], "EML-016": ["REJECT"],
    "EML-017": ["REJECT"], "EML-018": ["NEEDS_PERSON"], "EML-019": ["ALREADY_LOGGED"], "EML-020": ["ALREADY_LOGGED"],
    "EML-021": ["REJECT"], "EML-022": ["APPROVE"],
}


@pytest.mark.parametrize("eid,want", EXPECTED.items())
def test_email_outcomes(eid, want, monkeypatch):
    monkeypatch.setattr(g, "llm_available", lambda: False)
    assert [r["outcome"] for r in g.run_claim({"email_id": eid})["results"]] == want
