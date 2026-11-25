"""The P3 graph: one early-warning run per C&F in parallel, then the pick list, the §7.1 breach list and a short brief.

START -> plan -> check_cnf x N (via Send) -> assemble -> END
Code produces every number. No model is used (the brief is a template), so this graph needs no key and stores nothing.
"""
import operator
from datetime import date, timedelta
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

import config as C
from agent import stock as S


class CnfIn(TypedDict):
    cnf: str
    as_of: date


class State(TypedDict, total=False):
    as_of: date
    viewer: str                      # "all" (Kavita) or a C&F code (that region's RDM)
    cnfs: list[str]
    cnf_results: Annotated[list, operator.add]
    result: dict


def plan(state: State) -> dict:
    from agent import data as D
    D.get()   # load once here: parallel branches would each build their own copy
    as_of = state.get("as_of") or S.latest_date()
    all_cnfs = sorted({r["cnf"] for r in S.snapshots() if r["as_of"] == as_of})
    v = state.get("viewer") or "all"
    return {"as_of": as_of, "cnfs": all_cnfs if v == "all" else [c for c in all_cnfs if c == v]}


def fan_out(state: State):
    return [Send("check_cnf", {"cnf": c, "as_of": state["as_of"]}) for c in state["cnfs"]] or "assemble"


def check_cnf(inp: CnfIn) -> dict:
    w = S.watch(inp["as_of"], inp["cnf"])
    return {"cnf_results": [dict(cnf=inp["cnf"], summary=w["summary"].get(inp["cnf"]), batches=w["batches"])]}


def assemble(state: State) -> dict:
    as_of, res = state["as_of"], sorted(state.get("cnf_results", []), key=lambda r: r["cnf"])
    picks = {r["cnf"]: S.picklist(r["cnf"], as_of) for r in res if r["cnf"] in C.PICKLIST_TO}
    br = S.breaches(None if state.get("viewer", "all") == "all" else state["viewer"], since=as_of - timedelta(days=364))
    brief = []
    for r in res:
        s = r["summary"]
        if not s:
            continue
        brief.append(f"{s['cnf']} {s['city'] or ''}: {s['under_floor_share']:.0%} of stock value (₹{s['under_floor_value']/1e5:.1f} L) "
                     f"is under {C.RSL_FLOOR:.0%} RSL; another ₹{s['warn_value']/1e5:.1f} L is between {C.RSL_FLOOR:.0%} and {C.RSL_WARN:.0%}; "
                     f"₹{s['return_candidate_value']/1e5:.1f} L cannot sell before it reaches the floor (return to {C.CDC} and reallocate, never destroy)."
                     + (f" Owner: {s['rdm']}." if s["rdm"] else ""))
    return {"result": dict(as_of=as_of, viewer=state.get("viewer", "all"), cnfs=res, picklists=picks, breaches=br, brief=brief,
                           note="Breaches are flagged, not blocked (Kavita Rao, 20 Nov). Below 60% goes out only if the stockist agrees.")}


def build():
    g = StateGraph(State)
    g.add_node("plan", plan)
    g.add_node("check_cnf", check_cnf)
    g.add_node("assemble", assemble)
    g.add_edge(START, "plan")
    g.add_conditional_edges("plan", fan_out, ["check_cnf", "assemble"])
    g.add_edge("check_cnf", "assemble")
    g.add_edge("assemble", END)
    return g.compile()


_graph = None


def run_watch(viewer: str = "all", as_of: date | None = None) -> dict:
    global _graph
    _graph = _graph or build()
    init = {"viewer": viewer}
    if as_of:
        init["as_of"] = as_of
    return _graph.invoke(init)["result"]
