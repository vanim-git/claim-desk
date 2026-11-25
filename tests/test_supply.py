from datetime import date, timedelta

from fastapi.testclient import TestClient

from agent import schemes as X
from agent import supply as P
from agent.supply_graph import run_supply
from app import app

L4Q = X.last_date() - timedelta(days=364)


def test_unfilled_reproduces_the_discovery_figures():
    u = P.unfilled(L4Q)
    assert round(u["total"] / 1e7, 2) == 33.31 and round(u["conservative"] / 1e7, 2) == 30.77
    assert round(u["in_window"] / 1e7, 2) == 28.16 and round(u["outside_window"] / 1e7, 2) == 5.15
    assert round(u["by_quarter"]["FY27Q2"]["fill"] * 100, 1) == 84.8
    assert next(iter(u["by_cnf"])) == "CF-N02"                 # the largest shortfall


def test_scheme_window_is_the_22nd_to_month_end_of_quarter_end_months():
    ls = {(l["date"].month, l["date"].day): l["in_window"] for l in P.lines()}
    assert ls.get((9, 25)) is True and ls.get((9, 10)) is False and ls.get((10, 25)) is False


def test_shares_sum_to_one_and_show_the_shift():
    s = P.shares()
    assert abs(sum(v["current"] for v in s["by_cnf"].values()) - 1) < 1e-6 and abs(sum(v["proposed"] for v in s["by_cnf"].values()) - 1) < 1e-6
    assert s["by_cnf"]["CF-N02"]["gap"] > 0.04 and s["by_cnf"]["CF-E01"]["gap"] < -0.04   # N02 orders more, E01 less, than the FY25 split


def test_moves_come_from_spare_stock_only_and_go_via_the_cdc():
    m = P.moves()
    assert m["moves"] and all(x["from_cnf"] != x["to_cnf"] and x["via"] == "Bhiwandi" and x["packs"] > 0 for x in m["moves"])
    spare = {}
    from agent import stock as S
    held = {}
    for r in S.snapshots():
        if r["as_of"] == m["as_of"] and r["batch"]:
            held[(r["cnf"], r["sku"])] = held.get((r["cnf"], r["sku"]), 0) + r["qty"]
    out = {}
    for x in m["moves"]:
        out[(x["from_cnf"], x["sku"])] = out.get((x["from_cnf"], x["sku"]), 0) + x["packs"]
    assert all(v <= held[k] for k, v in out.items())


def test_graph_and_api():
    r = run_supply()
    assert round(r["unfilled"]["total"] / 1e7, 2) == 33.31 and r["moves"]["moves"] and len(r["notes"]) == 3
    j = TestClient(app).get("/api/supply-desk").json()
    assert j["shares"]["by_cnf"] and j["unfilled"]["by_quarter"]
