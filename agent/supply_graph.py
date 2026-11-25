"""The P1 graph: three independent analyses run in parallel, then one assembled answer for Kavita Rao.

START -> plan -> (unfilled | shares | moves) -> assemble -> END
Code produces every number. No model, no key, nothing stored. Proposals only: a person approves any move or any change of shares."""
from datetime import date, timedelta
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from agent import data as D
from agent import schemes as X
from agent import supply as P


class State(TypedDict, total=False):
    as_of: date
    unfilled: dict
    shares: dict
    moves: dict
    result: dict


def plan(state: State) -> dict:
    D.get(); X.sales(); P.lines()   # load once here: parallel branches would each build their own copy
    return {"as_of": state.get("as_of") or X.last_date()}


def n_unfilled(state: State) -> dict:
    return {"unfilled": P.unfilled(state["as_of"] - timedelta(days=364))}


def n_shares(state: State) -> dict:
    return {"shares": P.shares(state["as_of"])}


def n_moves(state: State) -> dict:
    return {"moves": P.moves()}


def assemble(state: State) -> dict:
    u, s, m = state["unfilled"], state["shares"], state["moves"]
    return {"result": dict(as_of=state["as_of"], unfilled=u, shares=dict(s, rows=[r for r in s["rows"] if abs(r["gap"]) >= 0.05]),
                           moves=m, notes=[
        f"₹{u['total']/1e7:.2f} cr unfilled in the last four quarters (₹{u['conservative']/1e7:.2f} cr counting repeat orders once); "
        f"₹{u['outside_window']/1e7:.2f} cr falls outside the scheme windows, where re-allocation can help.",
        "Production (about 0.74 of orders) and scheme-window demand are not fixed by allocation.",
        "Shares and moves are proposals for Kavita Rao; she approves moves the same day and changes shares from the next cycle."])}


def build():
    g = StateGraph(State)
    for name, fn in (("plan", plan), ("unfilled", n_unfilled), ("shares", n_shares), ("moves", n_moves), ("assemble", assemble)):
        g.add_node(name, fn)
    g.add_edge(START, "plan")
    for n in ("unfilled", "shares", "moves"):
        g.add_edge("plan", n)
        g.add_edge(n, "assemble")
    g.add_edge("assemble", END)
    return g.compile()


_graph = None


def run_supply(as_of: date | None = None) -> dict:
    global _graph
    _graph = _graph or build()
    return _graph.invoke({"as_of": as_of} if as_of else {})["result"]
