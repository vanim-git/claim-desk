"""The P2 graph: the per-SKU scheme-vs-expiry table, the §4.4 free-goods check, and a stock screen of every stockist per scheme SKU.

START -> plan -> screen_sku x N (via Send, one per scheme SKU) -> assemble -> END
Code produces every number. No model, no key, nothing stored. It warns the RSM list; it never blocks a scheme (Arjun Sethi, 20 Nov).
"""
import operator
from datetime import date
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

import config as C
from agent import data as D
from agent import schemes as X


class SkuIn(TypedDict):
    sku: str
    as_of: date


class State(TypedDict, total=False):
    as_of: date
    skus: list[str]
    sku_warns: Annotated[list, operator.add]
    result: dict


def plan(state: State) -> dict:
    D.get(); X._by_pair()   # load once here: parallel branches would each build their own copy
    return {"as_of": state.get("as_of") or X.last_date(), "skus": sorted({s["sku"] for s in X.sales() if s["scheme"]})}


def fan_out(state: State):
    return [Send("screen_sku", {"sku": k, "as_of": state["as_of"]}) for k in state["skus"]]


def screen_sku(inp: SkuIn) -> dict:
    stockists = sorted({st for (st, sk), rows in X._by_pair().items() if sk == inp["sku"]
                        and any(0 < (inp["as_of"] - r["date"]).days <= 91 for r in rows)})
    out = []
    for st in stockists:
        r = X.screen(st, inp["sku"], inp["as_of"])
        if r["warnings"]:
            home = D.get().stockist.get(st, {})
            out.append(dict(r, cnf=home.get("cnf"), stockist_name=home.get("stockist_name")))
    return {"sku_warns": out}


def assemble(state: State) -> dict:
    warns = sorted(state.get("sku_warns", []), key=lambda w: (w["cnf"] or "", -(w["est_stock_months"] or 0)))
    by_cnf = {}
    for w in warns:
        by_cnf.setdefault(w["cnf"], []).append(w)
    foc = X.foc_by_quarter()
    return {"result": dict(as_of=state["as_of"], sku_table=X.sku_table(), foc=foc[-8:], warnings=warns,
                           by_cnf={k: len(v) for k, v in by_cnf.items()},
                           notes=["Warn only: the scheme desk decides (Arjun Sethi, 20 Nov).",
                                  "Stock is an estimate from purchases; there is no secondary data (§4.5 note).",
                                  f"Data ends {X.last_date()}; the monthly SAP export will extend it."])}


def build():
    g = StateGraph(State)
    g.add_node("plan", plan)
    g.add_node("screen_sku", screen_sku)
    g.add_node("assemble", assemble)
    g.add_edge(START, "plan")
    g.add_conditional_edges("plan", fan_out, ["screen_sku"])
    g.add_edge("screen_sku", "assemble")
    g.add_edge("assemble", END)
    return g.compile()


_graph = None


def run_schemes(as_of: date | None = None) -> dict:
    global _graph
    _graph = _graph or build()
    return _graph.invoke({"as_of": as_of} if as_of else {})["result"]
