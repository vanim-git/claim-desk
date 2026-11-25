from datetime import date, timedelta

from fastapi.testclient import TestClient

import config as C
from agent import schemes as X
from agent.schemes_graph import run_schemes
from app import app


def test_data_ends_30_sep_2026():
    assert X.last_date() == date(2026, 9, 30)
    assert X.fy_q(date(2026, 9, 30)) == "FY27Q2" and X.fy_q(date(2026, 4, 1)) == "FY27Q1" and X.fy_q(date(2026, 3, 31)) == "FY26Q4"


def test_sku_table_reproduces_the_discovery_figures():
    t = X.sku_table()
    rows = t["rows"]
    assert len(rows) == 15                                    # the 15 SKUs that ever carry a quarter-end scheme
    assert round(t["baseline_rate"] * 100, 2) == 0.35         # non-scheme SKUs
    assert round(sum(r["claims"] for r in rows) / sum(r["sales"] for r in rows) * 100, 1) == 4.2
    assert 4.6e7 < t["total_extra_per_year"] < 4.8e7          # about ₹4.7 crore a year (₹4.76 cr in the note included rejected claims)
    assert rows == sorted(rows, key=lambda r: -r["extra_cost"])


def test_foc_cap_by_quarter():
    q = {x["quarter"]: x for x in X.foc_by_quarter()}
    assert round(q["FY27Q2"]["share"] * 100, 2) == 2.82 and not q["FY27Q2"]["over_cap"]
    assert q["FY27Q1"]["over_cap"] and q["FY27Q1"]["over_by"] > 0


def test_screen_warns_but_never_blocks():
    w = [o for o in X.scheme_orders("QS-FY27Q2") if o["warnings"]]
    assert w
    r = X.screen(w[0]["stockist"], w[0]["sku"], date(2026, 9, 1), 1)
    assert r["warnings"] and r["blocked"] is False and C.SCHEME_BLOCKS is False


def test_minimum_order_rule():
    # find a pair with 3 months of history; order below 1.5x the average of the previous 3 months warns, at 1.5x does not
    o = next(x for x in X.scheme_orders("QS-FY27Q2") if x["avg_paid_3m"] > 0)
    as_of = date(2026, 9, 1)
    low = X.screen(o["stockist"], o["sku"], as_of, o["minimum_order"] - 1)
    ok = X.screen(o["stockist"], o["sku"], as_of, o["minimum_order"])
    assert any("minimum" in x for x in low["warnings"]) and not any("minimum" in x for x in ok["warnings"])


def test_unknown_normal_month_goes_to_the_rsm():
    r = X.screen("STK9999", "PFL1001", date(2026, 9, 1))
    assert r["est_stock_months"] is None and any("RSM to confirm" in x for x in r["warnings"])


def test_graph_and_api():
    r = run_schemes()
    assert len(r["sku_table"]["rows"]) == 15 and r["warnings"] and set(r["by_cnf"]) <= {"CF-E01", "CF-N01", "CF-N02", "CF-S01", "CF-S02", "CF-W01"}
    c = TestClient(app)
    j = c.get("/api/scheme-desk").json()
    assert j["sku_table"]["rows"] and c.get("/api/scheme-desk", params={"as_of": "bad"}).status_code == 422
