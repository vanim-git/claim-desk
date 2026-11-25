"""P3 rules in plain Python: which C&F stock is heading under 60% remaining shelf life (RSL), what can still sell, the
oldest-first pick list, and dispatches already made under 60%. Reads data/ only; no model is used for any number."""
import csv
from datetime import date

import config as C
from agent import data as D
from agent import schemes as X

def cnf_code(s: str) -> str:
    s = (s or "").strip().upper().replace("-", "")
    return f"{s[:2]}-{s[2:]}" if len(s) == 5 else s


def rsl(expiry: date, as_of: date, shelf_months: float) -> float:
    return (expiry - as_of).days / (shelf_months * C.DAYS_PER_MONTH)


def band(r: float) -> str:
    return "breach" if r < C.RSL_FLOOR else "warn" if r < C.RSL_WARN else "ok"


_cache = {}


def snapshots() -> list[dict]:
    """All stock-snapshot rows, cleaned (dates, C&F codes), exact duplicates dropped. Rows with no batch are stock-outs."""
    if "s" in _cache:
        return _cache["s"]
    with open(D.DATA / "cnf_stock_snapshot.csv", newline="", encoding="utf-8") as f:
        raw = list(csv.DictReader(f))
    out, seen = [], set()
    for i, r in enumerate(raw, 1):
        k = tuple(r.values())
        if k in seen:
            continue
        seen.add(k)
        out.append(dict(row=i, as_of=D.to_date(r["snapshot_date"]), cnf=cnf_code(r["cnf_code"]), city=r["cnf_city"].strip(), sku=D.code(r["sku_code"]),
                        batch=D.code(r["batch_no"]) or None, expiry=D.to_date(r["expiry_date"]),
                        qty=D.to_num(r["qty_on_hand_packs"]) or 0, outward=D.to_num(r["avg_monthly_outward_packs"]) or 0))
    _cache["s"] = out
    return out


def latest_date() -> date:
    return max(r["as_of"] for r in snapshots() if r["as_of"])


def outward_by_pair(as_of: date) -> dict:
    """Monthly outward per (C&F, SKU), worked out from invoices: the median of the last OUTWARD_MONTHS calendar months of paid packs
    up to and including the month of `as_of`. Free packs are left out (scheme loading). The snapshot field is the fallback."""
    key = ("o", as_of, C.OUTWARD_MONTHS)
    if key in _cache:
        return _cache[key]
    months = []
    y, m = as_of.year, as_of.month
    for _ in range(C.OUTWARD_MONTHS):
        months.append((y, m))
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    paid = {}
    for s in X.sales():
        if s["date"] and (s["date"].year, s["date"].month) in months:
            k = (s["cnf"], s["sku"], s["date"].year, s["date"].month)
            paid[k] = paid.get(k, 0.0) + s["paid"]
    pairs = {(c, k) for (c, k, _, _) in paid}
    out = {}
    for c, k in pairs:
        v = sorted(paid.get((c, k, yy, mm), 0.0) for yy, mm in months)
        n = len(v)
        out[(c, k)] = v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2
    _cache[key] = out
    return out


def outward_for(cnf: str, sku: str, as_of: date, snapshot_value: float) -> float:
    if not C.OUTWARD_FROM_INVOICES:
        return snapshot_value
    return outward_by_pair(as_of).get((cnf, sku), snapshot_value)


def sellable(batches: list[dict], outward: float, as_of: date) -> list[dict]:
    """Oldest expiry first, the way a FEFO pick would run. A batch can sell only until it reaches the floor
    (60% RSL); sales in that time come from the monthly outward rate and go to the oldest batch first.
    Returns each batch with `can_sell` (packs expected to leave before the floor) and `excess` (the rest)."""
    sold_so_far, res = 0.0, []
    for b in sorted(batches, key=lambda x: x["expiry"]):
        floor_day = b["floor_date"]
        months_left = max((floor_day - as_of).days, 0) / C.DAYS_PER_MONTH
        room = max(outward * months_left - sold_so_far, 0)
        can = min(b["qty"], room)
        sold_so_far += can
        res.append(dict(b, can_sell=round(can), excess=round(b["qty"] - can)))
    return res


def watch(as_of: date | None = None, cnf: str | None = None) -> dict:
    """Weekly early-warning: every batch at or under 70% RSL, batch by batch, with what can still sell and what should go back."""
    d = D.get()
    as_of = as_of or latest_date()
    rows = [r for r in snapshots() if r["as_of"] == as_of and (cnf is None or r["cnf"] == cnf)]
    merged = {}   # the snapshot can list one batch on two lines (e.g. two locations): add them up
    for r in rows:
        if r["batch"] and r["expiry"] and r["qty"] > 0:
            k = (r["cnf"], r["sku"], r["batch"])
            if k in merged:
                merged[k] = dict(merged[k], qty=merged[k]["qty"] + r["qty"])
            else:
                merged[k] = r
    stock = list(merged.values())
    by_pair = {}
    for r in stock:
        sk = d.sku.get(r["sku"])
        if not sk or not sk["shelf"]:
            continue
        pts = sk["pts"] or 0
        shelf = sk["shelf"]
        floor_date = date.fromordinal(r["expiry"].toordinal() - round(shelf * C.DAYS_PER_MONTH * C.RSL_FLOOR))
        b = dict(cnf=r["cnf"], sku=r["sku"], product=sk["product_description"], batch=r["batch"], expiry=r["expiry"],
                 qty=r["qty"], value=r["qty"] * pts, rsl=rsl(r["expiry"], as_of, shelf), floor_date=floor_date,
                 outward=r["outward"], row=r["row"])
        b["band"] = band(b["rsl"])
        by_pair.setdefault((r["cnf"], r["sku"]), []).append(b)
    out, summary = [], {}
    for (c, s), bs in by_pair.items():
        outward = outward_for(c, s, as_of, bs[0]["outward"])
        tot = sum(b["qty"] for b in bs)
        cover = tot / outward if outward else None
        for b in sellable(bs, outward, as_of):
            b["cover_months"] = cover
            if b["band"] == "ok" and b["excess"] == 0:
                continue
            b["over_buffer"] = bool(cover and cover > C.BUFFER_MONTHS)
            b["action"] = ("sell first" if b["excess"] == 0 else
                           "return to CDC and reallocate" if b["can_sell"] == 0 else "sell first, return the excess")
            out.append(b)
    for c in {r["cnf"] for r in rows}:
        allv = sum(r["qty"] * (d.sku.get(r["sku"], {}).get("pts") or 0) for r in stock if r["cnf"] == c)
        low = sum(b["value"] for bs in by_pair.values() for b in bs if b["cnf"] == c and b["band"] == "breach")
        warn = sum(b["value"] for bs in by_pair.values() for b in bs if b["cnf"] == c and b["band"] == "warn")
        ret = sum(b["excess"] * (d.sku[b["sku"]]["pts"] or 0) for b in out if b["cnf"] == c)
        summary[c] = dict(cnf=c, city=next((r["city"] for r in rows if r["cnf"] == c), None), rdm=C.RDM.get(c), stock_value=allv, under_floor_value=low,
                          under_floor_share=(low / allv if allv else 0), warn_value=warn, return_candidate_value=ret)
    out.sort(key=lambda b: (b["cnf"], b["rsl"]))
    return dict(as_of=as_of, batches=out, summary=summary, clause="§7.1, " + C.POLICY)


def picklist(cnf: str, as_of: date | None = None) -> dict:
    """Manual oldest-batch pick list for one C&F until the WMS batch rule is live: per SKU, lowest expiry first."""
    d = D.get()
    as_of = as_of or latest_date()
    items = {}
    for r in snapshots():
        if r["as_of"] == as_of and r["cnf"] == cnf and r["batch"] and r["expiry"] and r["qty"] > 0 and r["sku"] in d.sku:
            items.setdefault(r["sku"], []).append(r)
    lines = []
    for sku, rs in sorted(items.items()):
        s = d.sku[sku]
        for n, r in enumerate(sorted(rs, key=lambda x: x["expiry"]), 1):
            x = rsl(r["expiry"], as_of, s["shelf"])
            lines.append(dict(sku=sku, product=s["product_description"], pick_order=n, batch=r["batch"], expiry=r["expiry"],
                              qty=r["qty"], rsl=x, band=band(x)))
    return dict(cnf=cnf, as_of=as_of, lines=lines, **C.PICKLIST_TO.get(cnf, {}),
                instruction="Pick in pick_order: lowest expiry first, per SKU. Confirm back within the stated days.")


def breaches(cnf: str | None = None, since: date | None = None, until: date | None = None) -> dict:
    """Dispatches (invoice lines) with RSL below the floor at invoice date: each is a breach (§7.1), none is blocked."""
    d = D.get()
    seen, rows = set(), []
    for lines in d.lines.values():
        for ln in lines:
            if ln["row"] in seen:
                continue
            seen.add(ln["row"])
            b, sk = d.batch.get(ln["batch"]), d.sku.get(ln["sku"])
            if not (b and b["expiry"] and sk and sk["shelf"] and ln["date"]):
                continue
            if (cnf and ln["cnf"] != cnf) or (since and ln["date"] < since) or (until and ln["date"] > until):
                continue
            x = rsl(b["expiry"], ln["date"], sk["shelf"])
            if x < C.RSL_FLOOR:
                rows.append(dict(invoice=ln["invoice_no"], date=ln["date"], cnf=ln["cnf"], stockist=ln["stockist"], sku=ln["sku"],
                                 batch=ln["batch"], packs=ln["packs"], rsl=x, value=ln["packs"] * (sk["pts"] or 0), row=ln["row"],
                                 blocked=C.BLOCK_BELOW_FLOOR))
    rows.sort(key=lambda r: r["date"])
    by = {}
    for r in rows:
        e = by.setdefault(r["cnf"], dict(cnf=r["cnf"], lines=0, value=0.0))
        e["lines"] += 1
        e["value"] += r["value"]
    return dict(lines=rows, by_cnf=by, total_value=sum(r["value"] for r in rows), clause="§7.1, " + C.POLICY)
