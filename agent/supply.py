"""P1 rules in plain Python: how much of each order went unfilled, where it fell (inside or outside the scheme windows),
how the allocation shares compare with what each C&F's stockists order, and which spare stock could cover unmet need through the CDC.
Reads data/ only. A person (Kavita Rao) approves any move or any change of shares."""
from collections import defaultdict
from datetime import date, timedelta

import config as C
from agent import data as D
from agent import schemes as X
from agent import stock as S

_c = {}


def lines() -> list[dict]:
    """One row per invoice and SKU: ordered (largest ordered_qty on the invoice), supplied (invoiced + free), unfilled packs and value.
    ordered_qty includes the free packs, so fill = (invoiced + free) / ordered."""
    if "l" in _c:
        return _c["l"]
    g = {}
    for s in X.sales():
        if not s["date"]:
            continue
        e = g.setdefault((s["invoice"], s["sku"]), dict(invoice=s["invoice"], sku=s["sku"], date=s["date"], cnf=s["cnf"],
                                                         stockist=s["stockist"], ordered=0.0, supplied=0.0, pts=s["pts"]))
        e["ordered"] = max(e["ordered"], s["ordered"])
        e["supplied"] += s["paid"] + s["free"]
    out = []
    for e in g.values():
        e["unfilled"] = max(e["ordered"] - e["supplied"], 0)
        e["unfilled_value"] = e["unfilled"] * e["pts"]
        e["in_window"] = e["date"].month in C.SCHEME_MONTHS and e["date"].day >= C.SCHEME_WINDOW_FROM_DAY
        e["quarter"] = X.fy_q(e["date"])
        out.append(e)
    _c["l"] = out
    return out


def _conservative(ls):
    """Repeat orders for the same unmet quantity count once: the largest single line per stockist, SKU and month (Arjun, 20 Nov)."""
    best = {}
    for l in ls:
        k = (l["stockist"], l["sku"], l["date"].year, l["date"].month)
        if k not in best or l["unfilled_value"] > best[k]["unfilled_value"]:
            best[k] = l
    return list(best.values())


def unfilled(since: date | None = None) -> dict:
    ls = [l for l in lines() if since is None or l["date"] >= since]
    tot = sum(l["unfilled_value"] for l in ls)
    by_q, by_c = defaultdict(lambda: dict(ordered=0.0, supplied=0.0, unfilled_value=0.0)), defaultdict(float)
    for l in ls:
        q = by_q[l["quarter"]]
        q["ordered"] += l["ordered"]
        q["supplied"] += min(l["supplied"], l["ordered"])
        q["unfilled_value"] += l["unfilled_value"]
        by_c[l["cnf"]] += l["unfilled_value"]
    win = sum(l["unfilled_value"] for l in ls if l["in_window"])
    return dict(total=tot, conservative=sum(l["unfilled_value"] for l in _conservative(ls)), in_window=win, outside_window=tot - win,
                by_quarter={q: dict(v, fill=v["supplied"] / v["ordered"] if v["ordered"] else None) for q, v in sorted(by_q.items())},
                by_cnf=dict(sorted(by_c.items(), key=lambda kv: -kv[1])))


def shares(asof: date | None = None) -> dict:
    """Allocation share of each C&F by SKU: the FY25 share still in use (packs dispatched in FY25) against a proposal on ordered packs
    incl. free over the last six months, repeats once, scheme spikes capped. Gap = proposed - current, in share points."""
    asof = asof or X.last_date()
    start = date(asof.year, asof.month, 1)
    for _ in range(C.ALLOC_LOOKBACK_MONTHS - 1):
        start = (start - timedelta(days=1)).replace(day=1)
    cur, mon = defaultdict(float), defaultdict(lambda: defaultdict(float))
    for l in lines():
        if X.fy_q(l["date"]).startswith(C.BASE_SHARE_FY):
            cur[(l["sku"], l["cnf"])] += l["supplied"]
    for l in _conservative_ordered(lines(), start):
        mon[(l["sku"], l["cnf"])][(l["date"].year, l["date"].month)] += l["ordered"]
    new = {}
    for k, m in mon.items():
        v = sorted(m.values())
        med = v[len(v) // 2]
        new[k] = sum(min(x, C.ALLOC_SPIKE_CAP * med) if med else x for x in v)
    skus = sorted({k[0] for k in list(cur) + list(new)})
    cnfs = sorted({k[1] for k in list(cur) + list(new)})
    rows = []
    for sk in skus:
        ct, nt = sum(cur[(sk, c)] for c in cnfs), sum(new.get((sk, c), 0) for c in cnfs)
        for c in cnfs:
            a, b = (cur[(sk, c)] / ct if ct else 0), (new.get((sk, c), 0) / nt if nt else 0)
            rows.append(dict(sku=sk, cnf=c, current=a, proposed=b, gap=b - a))
    pts = {k: (D.get().sku.get(k) or {}).get("pts") or 0 for k in skus}
    tot_cur = sum(cur[(sk, c)] * pts[sk] for sk in skus for c in cnfs)
    tot_new = sum(new.get((sk, c), 0) * pts[sk] for sk in skus for c in cnfs)
    by_cnf = {c: dict(cnf=c, current=sum(cur[(sk, c)] * pts[sk] for sk in skus) / tot_cur,
                      proposed=sum(new.get((sk, c), 0) * pts[sk] for sk in skus) / tot_new) for c in cnfs}
    for v in by_cnf.values():
        v["gap"] = v["proposed"] - v["current"]
    return dict(rows=rows, by_cnf=by_cnf, window_from=start, as_of=asof, review=C.ALLOC_REVIEW,
                basis=f"ordered packs incl. free, repeats once, last {C.ALLOC_LOOKBACK_MONTHS} months, a month capped at {C.ALLOC_SPIKE_CAP} x the median; "
                      f"current = packs dispatched in {C.BASE_SHARE_FY}; value at PTS")


def _conservative_ordered(ls, start):
    best = {}
    for l in ls:
        if l["date"] >= start:
            k = (l["stockist"], l["sku"], l["date"].year, l["date"].month)
            if k not in best or l["ordered"] > best[k]["ordered"]:
                best[k] = l
    return list(best.values())


def moves(as_of: date | None = None, months: int = 3) -> dict:
    """Unmet need (average monthly unfilled packs in the last `months` months, per C&F and SKU) matched with spare stock
    (closing stock above 2 months of outward) at other C&Fs, through the CDC. A proposal for Kavita; nothing moves by itself."""
    as_of = as_of or S.latest_date()
    since = as_of - timedelta(days=int(months * C.DAYS_PER_MONTH))
    need = defaultdict(float)
    for l in lines():
        if since < l["date"] <= as_of:
            need[(l["cnf"], l["sku"])] += l["unfilled"] / months
    held, outward = defaultdict(float), {}
    for r in S.snapshots():
        if r["as_of"] == as_of and r["batch"]:
            held[(r["cnf"], r["sku"])] += r["qty"]
        if r["as_of"] == as_of:
            outward[(r["cnf"], r["sku"])] = r["outward"]
    spare = {k: max(held[k] - C.SPARE_BUFFER_MONTHS * outward.get(k, 0), 0) for k in held}
    pts = lambda sk: (D.get().sku.get(sk) or {}).get("pts") or 0
    out = []
    for (rc, sk), n in sorted(need.items(), key=lambda kv: -kv[1] * pts(kv[0][1])):
        gap = n - held.get((rc, sk), 0)
        if gap <= 0:
            continue
        donors = sorted(((c, spare[(c, s)]) for (c, s) in spare if s == sk and c != rc and spare[(c, s)] > 0), key=lambda x: -x[1])
        for dc, avail in donors:
            q = min(gap, avail)
            if q < 1:
                continue
            out.append(dict(sku=sk, from_cnf=dc, to_cnf=rc, packs=round(q), value=q * pts(sk), via=C.CDC, days=C.TRANSFER_DAYS))
            spare[(dc, sk)] -= q
            gap -= q
            if gap < 1:
                break
    short = sum(max(n - held.get(k, 0), 0) * pts(k[1]) for k, n in need.items())
    return dict(as_of=as_of, moves=out, covered_value=sum(m["value"] for m in out), unmet_value=short,
                note=f"Approval is same day (Kavita Rao); the move takes {C.TRANSFER_DAYS} days; stock goes to the CDC, never C&F to C&F. "
                     "Take the oldest batches first (see Expiry watch).")
