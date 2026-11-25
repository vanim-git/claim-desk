from datetime import date

from fastapi.testclient import TestClient

import config as C
from agent import data as D
from agent import schemes as X
from agent import stock as S
from agent import supply as P
from app import app

c = TestClient(app)


def test_outward_comes_from_invoices_and_is_larger_than_the_snapshot_field():
    as_of = S.latest_date()
    inv = S.outward_by_pair(as_of)
    snap = {(r["cnf"], r["sku"]): r["outward"] for r in S.snapshots() if r["as_of"] == as_of and r["outward"]}
    both = [k for k in snap if inv.get(k)]
    assert len(both) > 100
    ratios = sorted(snap[k] / inv[k] for k in both)
    assert ratios[len(ratios) // 2] < 0.6          # the snapshot field understates outward (about 0.35 of invoiced paid packs)


def test_outward_is_the_median_of_six_months_of_paid_packs():
    as_of = date(2026, 9, 30)
    k = next(iter(S.outward_by_pair(as_of)))
    months = [(2026, 9), (2026, 8), (2026, 7), (2026, 6), (2026, 5), (2026, 4)]
    paid = {m: 0.0 for m in months}
    for s in X.sales():
        if (s["cnf"], s["sku"]) == k and s["date"] and (s["date"].year, s["date"].month) in paid:
            paid[(s["date"].year, s["date"].month)] += s["paid"]
    v = sorted(paid.values())
    assert S.outward_by_pair(as_of)[k] == (v[2] + v[3]) / 2


def test_switch_back_to_snapshot_field(monkeypatch):
    monkeypatch.setattr(C, "OUTWARD_FROM_INVOICES", False)
    assert S.outward_for("CF-E01", "PFL1001", date(2026, 9, 30), 123.0) == 123.0


def test_more_outward_means_less_spare_stock():
    C_old = C.OUTWARD_FROM_INVOICES
    try:
        C.OUTWARD_FROM_INVOICES = True
        inv = P.moves()["covered_value"]
        C.OUTWARD_FROM_INVOICES = False
        snap = P.moves()["covered_value"]
    finally:
        C.OUTWARD_FROM_INVOICES = C_old
    assert inv < snap


def test_sources_are_shown_for_p1_p2_p3():
    w = c.get("/api/expiry-watch").json()
    assert all("row" in b for cn in w["cnfs"] for b in cn["batches"])
    assert all("row" in r for r in w["breaches"]["lines"])
    s = c.get("/api/scheme-desk").json()
    ev = s["warnings"][0]["evidence"]
    assert ev["file"] == "primary_sales.csv" and ev["rows"] and ev["total_rows"] >= len(ev["rows"])
    m = c.get("/api/supply-desk").json()["moves"]["moves"][0]["evidence"]
    assert m["spare_at"]["rows"] and m["need_at"]["invoice_lines"]


def test_source_rows_really_are_the_rows_they_name():
    s = c.get("/api/scheme-desk").json()["warnings"][0]
    raw = D._rows("primary_sales")
    for r in s["evidence"]["rows"]:
        row = raw[r - 1]
        assert D.code(row["stockist_code"]) == s["stockist"] and D.code(row["sku_code"]) == s["sku"]


def test_digest_has_a_section_per_owner_and_matches_the_desks():
    d = c.get("/api/digest").json()
    assert [x["owner"] for x in d["sections"]][0] == "Kavita Rao"
    assert {i["tab"] for x in d["sections"] for i in x["items"]} <= {"claim", "stock", "schemes", "supply"}
    moves = c.get("/api/supply-desk").json()["moves"]
    assert f"{len(moves['moves'])} proposed moves" in d["sections"][0]["items"][0]["text"]
    pending = sum(1 for x in D.get().claims if x["status"] == "Pending")
    assert f"{pending} claims are pending" in d["sections"][-1]["items"][0]["text"]


def test_data_log_counts_the_fixes():
    f = c.get("/api/data-log").json()["files"]
    assert f["primary_sales.csv"]["exact_duplicate_rows_dropped"] > 0
    assert f["expiry_claims.csv"]["rows"] == len(D._rows("expiry_claims"))
    assert f["expiry_claims.csv"]["invoice_numbers_written_INV-"] > 0


def test_page_has_five_tabs_with_the_digest_last():
    html = c.get("/").text
    assert html.count('class="navtab') == 5 and 'data-page="digest"' in html and 'src="/digest.js"' in html
