"""The claim rules in plain Python. Each rule is a pure function (line, facts) -> RuleResult.

Status: pass / fail (policy says reject) / soft (a failure Finance wants a person to see,
set in config.py) / unknown (cannot be checked from the data: a person must look).
Limits come from config.py. No rule reads an email or calls a model.
"""
import re

import config as C


def _r(rule, status, detail="", evidence=None):
    return {"rule": rule, "clause": f"{C.CLAUSES[rule]}, {C.POLICY}", "status": status,
            "detail": detail, "evidence": evidence or []}


def _soft(action):  # config value "person" -> soft failure; "reject" -> hard failure
    return "soft" if action == "person" else "fail"


def r1_billed(line, f):
    if f["supplied_all"] > 0:
        return _r("R1", "pass", f"{f['supplied_all']:.0f} packs invoiced incl. free to {line['stockist']}", f["sales_evidence"])
    if not f["batch_sold_anywhere"]:
        return _r("R1", "unknown", "batch predates the sales data (archived before the ERP migration): escalate to a person, do not reject")
    return _r("R1", "fail", "batch was never invoiced to this stockist")


def r2_invoice(line, f):
    ref, inv = line.get("invoice_ref"), f["invoice"]
    if not ref:
        return _no_ref(line, f)
    if inv is None:
        return _r("R2", "unknown", f"{ref} not found in the sales data (may predate it): escalate, do not reject")
    ev = [{"file": "primary_sales.csv", "row": inv["row"], "invoice_no": ref}]
    if inv["stockist"] != line["stockist"] or line["batch"] not in inv["batches"]:
        return _r("R2", "fail", f"{ref} is for {inv['stockist']}, not this stockist and batch", ev)
    return _r("R2", "pass", ref, ev)


def _no_ref(line, f):
    """No invoice reference passes only if all three hold (Neha, 20 Nov): sales show the batch invoiced to this stockist,
    the quantity is within what was invoiced, and a written Area Manager approval names this claim number."""
    earlier = sum(c["qty"] or 0 for c in f["prior"])
    billed = f["supplied_asof"] > 0
    within = billed and line["qty"] + earlier <= f["supplied_asof"]
    text = line.get("am_approval") or ""
    named = re.search(r"CLM-\d{4}-\d{5}", text)
    approved = bool(named) and "approv" in text.lower() and (not line.get("claim_no") or named.group(0) == line["claim_no"])
    if billed and within and approved:
        return _r("R2", "pass", f"no invoice reference, but batch invoiced to this stockist, quantity within it, and approval names {named.group(0)}",
                  f["sales_evidence"])
    miss = [m for ok, m in ((billed, "batch not invoiced to this stockist in the sales data"),
                            (within, "quantity not within what was invoiced"),
                            (approved, "no written Area Manager approval naming the claim number")) if not ok]
    return _r("R2", "unknown", "no invoice reference (§5.4): " + "; ".join(miss), f["sales_evidence"])


def r3_window(line, f):
    exp, t = f["expiry"], line["claim_type"]
    cd = line.get("window_date") or line["claim_date"]   # a resubmission is judged on the original claim date (Neha, 20 Nov)
    ev = [f["expiry_evidence"]] if f["expiry_evidence"] else []
    if t in ("Near expiry", "Expired"):
        if exp is None:
            return _r("R3", "unknown", "expiry date not known")
        d = (cd - exp).days
        if t == "Near expiry":
            if -C.NE_WINDOW_DAYS <= d <= 0:
                return _r("R3", "pass", f"{-d} days before expiry", ev)
            if d < -C.NE_WINDOW_DAYS:
                return _r("R3", _soft(C.EARLY_NE_ACTION), f"{-d} days before expiry: lodged early", ev)
            if d <= C.EXPIRED_WINDOW_DAYS:
                return _r("R3", "unknown", f"lodged as near-expiry but expired {d} days ago: re-type as Expired", ev)
            return _r("R3", "fail", f"{d} days after expiry", ev)
        ok = 0 <= d <= C.EXPIRED_WINDOW_DAYS
        return _r("R3", "pass" if ok else "fail", f"{d} days after expiry", ev)
    inv = f["invoice"]
    if inv is None or inv["date"] is None:
        return _r("R3", "unknown", "no invoice date to test the 7-day window")
    d = (cd - inv["date"]).days
    return _r("R3", "pass" if d <= C.TRANSIT_WINDOW_DAYS else "fail", f"{d} days after invoice",
              [{"file": "primary_sales.csv", "row": inv["row"]}])


def r4_quantity(line, f):
    earlier = sum(c["qty"] or 0 for c in f["prior"])
    sup = f["supplied_asof"]
    if sup > 0 and line["qty"] + earlier > sup:
        return _r("R4", _soft(C.QTY_OVER_ACTION),
                  f"claimed {line['qty']:.0f} + earlier {earlier:.0f} > supplied {sup:.0f} (allowable {max(sup - earlier, 0):.0f})",
                  f["sales_evidence"])
    return _r("R4", "pass", f"claimed {line['qty']:.0f} + earlier {earlier:.0f} <= supplied {sup:.0f}", f["sales_evidence"])


def r5_earlier_claim(line, f):
    prior = f["prior"]
    ev = [{"file": "expiry_claims.csv", "row": c["row"], "claim_no": c["claim_no"]} for c in prior]
    same = [c for c in prior if c["qty"] == line["qty"]]
    if same:
        return _r("R5", "fail", "same quantity already claimed: " + ", ".join(
            f"{c['claim_no']} ({c['status']}{', ' + c['cn_no'] if c['cn_no'] else ''})" for c in same), ev)
    if prior:
        return _r("R5", "unknown", "earlier claim on this stockist and batch, different quantity: " + ", ".join(
            f"{c['claim_no']} ({c['qty']:.0f})" for c in prior), ev)
    return _r("R5", "pass", "no earlier claim")


def r6_cfa(line, f):
    ok = f["home_cfa"] == line["cnf"]
    return _r("R6", "pass" if ok else "fail", f"claim CFA {line['cnf']}, home CFA {f['home_cfa']}")


def r7_value(line, f):
    pts = f["pts"]
    if pts is None:
        return _r("R7", "unknown", "price not known")
    exp = line["qty"] * pts
    if line.get("value") is None:
        return _r("R7", "unknown", f"claim value blank; qty x PTS = {exp:.2f}")
    import config
    if abs(line["value"] - exp) <= config.VALUE_TOLERANCE_INR:
        return _r("R7", "pass", f"{line['value']:.2f} = qty x PTS")
    return _r("R7", "unknown", f"claim value {line['value']:.2f} differs from qty x PTS {exp:.2f}")


def r8_stated_expiry(line, f):
    s, exp = line.get("stated_expiry"), f["expiry"]
    if s is None or exp is None or not f["batch_in_master"]:
        return None
    if abs((s - exp).days) > C.STATED_EXPIRY_TOLERANCE_DAYS:
        return _r("R8", "unknown", f"stated expiry {s:%b %Y} differs from batch master {exp:%b %Y}: possible wrong batch")
    return _r("R8", "pass", "stated expiry matches the batch master")


RULES = [r1_billed, r2_invoice, r3_window, r4_quantity, r5_earlier_claim, r6_cfa, r7_value, r8_stated_expiry]


def run_checks(line, facts) -> list[dict]:
    """Every rule runs, even after one fails, so the reviewer sees the whole picture."""
    return [r for r in (rule(line, facts) for rule in RULES) if r]


FORCING_FLAGS = ("injection_suspected", "sender_unverified", "unit_converted", "batch_ambiguous", "parse_failed", "unit_unclear")


def decide(checks, flags=(), strict=False) -> str:
    """Reject if a rule fails; Needs a person if anything is soft/unknown or a forcing flag is set; else Approve.
    `strict` turns soft failures into hard ones (the audit of credited claims and the policy text)."""
    status = [("fail" if strict and c["status"] == "soft" else c["status"]) for c in checks]
    if "fail" in status:
        return "REJECT"
    if any(s in ("soft", "unknown") for s in status):
        return "NEEDS_PERSON"
    if any(fl in FORCING_FLAGS or fl.startswith("missing:") for fl in flags):
        return "NEEDS_PERSON"
    return "APPROVE"


def to_packs(qty: float, unit: str | None, per_box: int | None) -> float:
    """In this data a strip is one pack, whatever the word. Only boxes are converted."""
    if unit and unit.lower().startswith("box") and per_box:
        return qty * per_box
    return qty


def d0_in_email_duplicate(lines):
    """Same stockist, batch and quantity twice in one email: the later copies are rejected."""
    seen, unique, dups = set(), [], []
    for ln in lines:
        k = (ln.get("stockist"), ln.get("batch"), ln.get("qty"))
        if ln.get("batch") and k in seen:
            dups.append(ln)
        else:
            seen.add(k)
            unique.append(ln)
    return unique, dups


def d0_result():
    return _r("D0", "fail", "same line repeated inside this email")
