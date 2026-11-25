from datetime import date

from fastapi.testclient import TestClient

import config as C
from agent import stock as S
from agent.stock_graph import run_watch
from app import app

AS_OF = date(2026, 9, 30)


def test_latest_snapshot_and_cnf_codes_cleaned():
    assert S.latest_date() == AS_OF
    assert {r["cnf"] for r in S.snapshots()} == {"CF-E01", "CF-N01", "CF-N02", "CF-S01", "CF-S02", "CF-W01"}


def test_hooghly_under_floor_matches_brief():
    s = S.watch(AS_OF, "CF-E01")["summary"]["CF-E01"]
    assert round(s["under_floor_share"], 2) == 0.30
    assert 1.17e7 < s["under_floor_value"] < 1.19e7      # the ₹1.18 crore in the problem statement
    assert s["rdm"] == "Subhajit Banerjee"


def test_breaches_match_analysis():
    from datetime import timedelta
    b = S.breaches(since=AS_OF - timedelta(days=364))
    assert len(b["lines"]) == 1171 and round(b["total_value"] / 1e7, 2) == 6.28   # all six C&Fs, last four quarters
    assert len(b["by_cnf"]) == 6 and not any(r["blocked"] for r in b["lines"])
    assert round(S.breaches("CF-E01", since=date(2026, 2, 1))["total_value"] / 1e5, 1) == 94.8   # since the Feb-26 WMS go-live


def test_below_floor_batch_cannot_sell_and_is_returned():
    bs = [b for b in S.watch(AS_OF, "CF-E01")["batches"] if b["band"] == "breach"]
    assert bs and all(b["can_sell"] == 0 and b["excess"] == b["qty"] for b in bs if b["floor_date"] <= AS_OF)
    assert all("return" in b["action"] for b in bs if b["can_sell"] == 0)


def test_sellable_uses_oldest_first_and_outward_rate():
    mk = lambda e, q: dict(expiry=e, qty=q, floor_date=date(2027, 1, 1))   # about 3 months to the floor
    r = S.sellable([mk(date(2027, 6, 1), 1000), mk(date(2027, 3, 1), 2000)], 1000, date(2026, 9, 30))
    assert [x["expiry"] for x in r] == [date(2027, 3, 1), date(2027, 6, 1)]
    assert r[0]["can_sell"] == 2000 and r[1]["can_sell"] == 1000   # about 3 months x 1000 = 3000 packs sell, oldest first
    assert S.sellable([mk(date(2027, 3, 1), 5000)], 1000, AS_OF)[0]["excess"] == 5000 - round(1000 * 93 / C.DAYS_PER_MONTH)


def test_picklist_oldest_first_per_sku():
    p = S.picklist("CF-E01", AS_OF)
    assert p["to"] == "Pradip Ghosh" and p["cc"] == "Subhajit Banerjee" and p["confirm_within_days"] == 2
    by = {}
    for l in p["lines"]:
        by.setdefault(l["sku"], []).append(l)
    assert all([x["expiry"] for x in v] == sorted(x["expiry"] for x in v) and v[0]["pick_order"] == 1 for v in by.values())


def test_graph_viewer_scopes_regions():
    assert len(run_watch("all")["cnfs"]) == 6
    r = run_watch("CF-E01")
    assert [c["cnf"] for c in r["cnfs"]] == ["CF-E01"] and set(r["picklists"]) == {"CF-E01"} and C.BLOCK_BELOW_FLOOR is False


def test_api_route():
    c = TestClient(app)
    r = c.get("/api/expiry-watch", params={"viewer": "CF-E01"})
    assert r.status_code == 200 and r.json()["cnfs"][0]["cnf"] == "CF-E01"
    assert c.get("/api/expiry-watch", params={"as_of": "xx"}).status_code == 422
