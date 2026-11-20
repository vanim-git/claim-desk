from datetime import date, timedelta

from tests import rules_helpers as H
from agent import rules as R


def run(**kw):
    line, facts = H.make(**kw)
    return {c["rule"]: c["status"] for c in R.run_checks(line, facts)}


def test_clean_claim_approves():
    line, facts = H.make()
    assert R.decide(R.run_checks(line, facts)) == "APPROVE"


def test_r1_never_billed_fails_and_unsold_batch_unknown():
    assert run(supplied_all=0, sold_anywhere=True)["R1"] == "fail"
    assert run(supplied_all=0, sold_anywhere=False)["R1"] == "unknown"


def test_r2_invoice_missing_unknown_wrong_stockist_fail():
    assert run(invoice_ref=None)["R2"] == "unknown"
    assert run(invoice_stockist="STK9999")["R2"] == "fail"


def test_r3_near_expiry_boundaries():
    assert run(days_to_expiry=90)["R3"] == "pass"
    assert run(days_to_expiry=0)["R3"] == "pass"
    assert run(days_to_expiry=91)["R3"] == "fail"      # early: recommend reject (Neha, 20 Nov)
    assert run(days_to_expiry=-30)["R3"] == "unknown"  # already expired, wrong type


def test_r2_no_invoice_ref_needs_all_three_conditions():
    ok = "Approved by Area Manager: CLM-2611-00001"
    assert run(invoice_ref=None, am_approval=ok, claim_no="CLM-2611-00001")["R2"] == "pass"
    assert run(invoice_ref=None, am_approval="Approved.")["R2"] == "unknown"                  # does not name the claim
    assert run(invoice_ref=None, am_approval=ok, claim_no="CLM-2611-00002")["R2"] == "unknown"  # names another claim
    assert run(invoice_ref=None)["R2"] == "unknown"                                           # no approval
    assert run(invoice_ref=None, am_approval=ok, supplied_asof=0, sold_anywhere=True)["R2"] == "unknown"  # never invoiced to them
    assert run(invoice_ref=None, am_approval=ok, qty=101, supplied_asof=100)["R2"] == "unknown"           # above invoiced


def test_r1_batch_predating_data_is_escalated_not_rejected():
    line, facts = H.make(supplied_all=0, sold_anywhere=False)
    r = [c for c in R.run_checks(line, facts) if c["rule"] == "R1"][0]
    assert r["status"] == "unknown" and "predates" in r["detail"]


def test_r3_expired_window():
    assert run(claim_type="Expired", days_to_expiry=-90)["R3"] == "pass"
    assert run(claim_type="Expired", days_to_expiry=-91)["R3"] == "fail"
    assert run(claim_type="Expired", days_to_expiry=5)["R3"] == "fail"


def test_r3_transit_window_seven_days():
    assert run(claim_type="Breakage in transit", days_after_invoice=7)["R3"] == "pass"
    assert run(claim_type="Breakage in transit", days_after_invoice=8)["R3"] == "fail"


def test_r4_quantity_over_is_soft_and_boundary_passes():
    assert run(qty=100, supplied_asof=100)["R4"] == "pass"
    assert run(qty=101, supplied_asof=100)["R4"] == "fail"
    assert run(qty=60, supplied_asof=100, prior_qty=[50])["R4"] == "fail"


def test_r5_same_qty_fails_different_qty_unknown():
    assert run(prior_qty=[100])["R5"] == "fail"
    assert run(prior_qty=[40])["R5"] == "unknown"
    assert run(prior_qty=[])["R5"] == "pass"


def test_r6_wrong_cfa_fails():
    assert run(cnf="CF-X99")["R6"] == "fail"


def test_r7_value_mismatch_unknown():
    assert run(value=100 * 10.0)["R7"] == "pass"
    assert run(value=5000.0)["R7"] == "unknown"


def test_decide_priority_and_flags():
    fail = [{"status": "fail"}, {"status": "unknown"}]
    assert R.decide(fail) == "REJECT"
    assert R.decide([{"status": "soft"}]) == "NEEDS_PERSON"
    assert R.decide([{"status": "soft"}], strict=True) == "REJECT"
    assert R.decide([{"status": "pass"}], flags=["injection_suspected"]) == "NEEDS_PERSON"
    assert R.decide([{"status": "pass"}], flags=["missing:qty"]) == "NEEDS_PERSON"


def test_units_only_boxes_convert():
    assert R.to_packs(5, "strips", 10) == 5
    assert R.to_packs(5, "boxes", 10) == 50
    assert R.to_packs(5, "box", None) == 5


def test_d0_duplicate_inside_one_email():
    a = {"stockist": "S", "batch": "B1", "qty": 10}
    unique, dups = R.d0_in_email_duplicate([a, dict(a), dict(a, qty=11)])
    assert len(unique) == 2 and len(dups) == 1
