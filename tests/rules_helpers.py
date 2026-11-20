"""Builds a clean line and its facts, so each test changes one thing."""
from datetime import date, timedelta


def make(qty=100, claim_type="Near expiry", days_to_expiry=30, days_after_invoice=3, supplied_all=100, supplied_asof=100,
         sold_anywhere=True, invoice_ref="INV/1", invoice_stockist="STK1", prior_qty=(), cnf="CF-A", value=None, pts=10.0, am_approval=None, claim_no=None):
    cd = date(2026, 3, 10)
    line = dict(stockist="STK1", batch="B1", qty=qty, claim_type=claim_type, claim_date=cd, invoice_ref=invoice_ref, cnf=cnf,
                value=qty * pts if value is None else value, stated_expiry=None, am_approval=am_approval, claim_no=claim_no)
    inv = None if invoice_ref is None else dict(date=cd - timedelta(days=days_after_invoice), stockist=invoice_stockist,
                                                 batches={"B1"}, row=1)
    facts = dict(supplied_all=supplied_all, supplied_asof=supplied_asof, sales_evidence=[], batch_sold_anywhere=sold_anywhere,
                 invoice=inv, expiry=cd + timedelta(days=days_to_expiry), expiry_evidence={"file": "batch_master.csv", "row": 1},
                 prior=[dict(qty=q, row=2, claim_no=f"C{i}", status="Credited", cn_no=None) for i, q in enumerate(prior_qty)],
                 home_cfa="CF-A", pts=pts, batch_in_master=True)
    return line, facts
