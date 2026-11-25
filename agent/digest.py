"""Weekly digest: one short section per owner, put together from the P1-P3 results. Read-only: nothing is stored or sent;
a person opens the page, or a scheduler can call the endpoint later. Every line is code-made text from numbers already computed
by the desk it points to (`tab`), so the line and the table behind it cannot disagree."""
import config as C
from agent import data as D
from agent.schemes_graph import run_schemes
from agent.stock_graph import run_watch
from agent.supply_graph import run_supply

L = lambda v: f"₹{v / 1e5:.1f} L"
CR = lambda v: f"₹{v / 1e7:.2f} cr"


def build_digest() -> dict:
    w, sc, su = run_watch("all"), run_schemes(), run_supply()
    e01 = next((c["summary"] for c in w["cnfs"] if c["cnf"] == "CF-E01"), None)
    u, m = su["unfilled"], su["moves"]
    gaps = sorted(su["shares"]["by_cnf"].values(), key=lambda g: -abs(g["gap"]))[:2]
    foc = sc["foc"][-1]
    pend = [c for c in D.get().claims if c["status"] == "Pending"]
    pend_value = sum(c["value"] or 0 for c in pend)
    sections = [
        dict(owner="Kavita Rao", role="Supply Chain", items=[
            dict(tab="supply", text=f"{len(m['moves'])} proposed moves through {C.CDC} could cover {L(m['covered_value'])} of {CR(m['unmet_value'])} a month of unmet need. Your approval is needed."),
            dict(tab="supply", text=f"{CR(u['outside_window'])} of the last four quarters' unfilled orders fell outside the scheme windows, where re-allocation can help."),
            dict(tab="stock", text=f"Network: {CR(sum(c['summary']['return_candidate_value'] for c in w['cnfs'] if c['summary']))} of stock cannot sell before it reaches 60% RSL."),
        ]),
        dict(owner="Subhajit Banerjee and Pradip Ghosh", role="Hooghly (CF-E01)", items=[
            dict(tab="stock", text=(f"{e01['under_floor_share']:.0%} of stock value ({L(e01['under_floor_value'])}) is under 60% RSL; {L(e01['warn_value'])} more is between 60% and 70%. "
                                    f"Return candidates: {L(e01['return_candidate_value'])}.") if e01 else "No Hooghly stock in the snapshot."),
            dict(tab="stock", text=f"Oldest-first pick list is on the Expiry watch tab; confirm back within {C.PICKLIST_TO['CF-E01']['confirm_within_days']} days."),
        ]),
        dict(owner="Arjun Sethi", role="Sales", items=[
            dict(tab="schemes", text=f"{len(sc['warnings'])} stockist-SKU pairs show estimated stock above {C.STOCK_NORM_MONTHS} months before the next scheme (warn the RSM, do not block)."),
            dict(tab="schemes", text=f"Free goods in {foc['quarter']}: {foc['share']:.2%} of primary sales at PTS against the {C.FOC_CAP:.0%} cap" + (" (over: CFO approval, §4.4)." if foc["over_cap"] else ".")),
        ]),
        dict(owner="Vaishali Kapoor", role="Demand Planning", items=[
            dict(tab="supply", text="Largest gaps between the FY25 share and the proposed share: " + "; ".join(f"{g['cnf']} {g['current']:.1%} to {g['proposed']:.1%}" for g in gaps) + ". Review is quarterly."),
        ]),
        dict(owner="Neha Bansal", role="Commercial Finance", items=[
            dict(tab="claim", text=f"{len(pend)} claims are pending in the register ({CR(pend_value)}). Run them on the Claim desk tab; a person decides each."),
        ]),
    ]
    return dict(as_of=su["as_of"], sections=sections,
                note="Read-only. Nothing is stored or sent; each line comes from the desk named by its link.")
