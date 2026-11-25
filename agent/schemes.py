"""P2 rules in plain Python: what quarter-end scheme stock costs in expiry claims, SKU by SKU, and which stockists a scheme
should warn the RSM about. Reads data/ only. Warns, never blocks (Arjun Sethi, 20 Nov)."""
from collections import defaultdict
from datetime import date, timedelta

import config as C
from agent import data as D

_c = {}


def sales() -> list[dict]:
    """primary_sales lines, cleaned like data.py (exact duplicates dropped before and after normalising)."""
    if "s" in _c:
        return _c["s"]
    out, seen = [], set()
    for r in D._dedup(D._rows("primary_sales"), D._raw):
        code = (r["scheme_code"] or "").strip().upper()
        n = dict(invoice=r["invoice_no"].strip(), date=D.to_date(r["invoice_date"]), cnf=r["cnf_code"].strip(),
                 stockist=D.code(r["stockist_code"]), sku=D.code(r["sku_code"]), batch=D.code(r["batch_no"]) or None,
                 paid=D.to_num(r["invoiced_qty"]) or 0, ordered=D.to_num(r["ordered_qty"]) or 0, free=D.to_num(r["free_qty"]) or 0, pts=D.to_num(r["pts_inr"]) or 0,
                 net=D.to_num(r["net_value_inr"]) or 0, scheme=code if code.startswith("QS-") else None, row=r["row"])
        k = tuple(v for kk, v in n.items() if kk != "row")
        if k not in seen:
            seen.add(k)
            out.append(n)
    _c["s"] = out
    return out


def fy_q(d: date) -> str:
    fy = d.year + (1 if d.month >= 4 else 0)
    return f"FY{fy % 100}Q{((d.month - 4) % 12) // 3 + 1}"


def last_date() -> date:
    return max(s["date"] for s in sales() if s["date"])


def _claim_value(c) -> float:
    if c["value"] is not None:
        return c["value"]
    sk = D.get().sku.get(c["sku"])
    return (c["qty"] or 0) * ((sk or {}).get("pts") or 0)


def sku_table(since="default") -> dict:
    """Per scheme SKU: scheme-supplied stock, expiry claims on it, and the claim rate against SKUs that never carry a scheme.
    Extra cost = claims on the SKU - (non-scheme-SKU claim rate x the SKU's sales). The December list is Arjun's decision."""
    d = D.get()
    if since == "default":
        since = last_date() - timedelta(days=364)   # last four quarters
    S = [x for x in sales() if since is None or (x["date"] and x["date"] >= since)]
    scheme_skus = {s["sku"] for s in S if s["scheme"]}
    sales_by, scheme_pairs = defaultdict(float), defaultdict(float)
    sch_val, foc_val = defaultdict(float), defaultdict(float)
    for s in S:
        sales_by[s["sku"]] += s["net"]
        if s["scheme"]:
            sch_val[s["sku"]] += (s["paid"] + s["free"]) * s["pts"]
            foc_val[s["sku"]] += s["free"] * s["pts"]
            if s["batch"]:
                scheme_pairs[(s["stockist"], s["batch"])] += s["free"] + s["paid"]
    claims, on_scheme = defaultdict(float), defaultdict(float)
    for c in d.claims:
        if (c["claim_type"] in C.SCHEME_CLAIM_TYPES and c["status"] in C.CLAIM_STATUS_COUNTED
                and (since is None or (c["claim_date"] and c["claim_date"] >= since))):
            v = _claim_value(c)
            claims[c["sku"]] += v
            if (c["stockist"], c["batch"]) in scheme_pairs:
                on_scheme[c["sku"]] += v
    non = [k for k in sales_by if k not in scheme_skus]
    base = sum(claims[k] for k in non) / sum(sales_by[k] for k in non)
    months = (last_date() - min(s["date"] for s in S if s["date"])).days / C.DAYS_PER_MONTH if since is None else 12.0
    rows = []
    for k in sorted(scheme_skus):
        sk = d.sku.get(k, {})
        rate = claims[k] / sales_by[k] if sales_by[k] else 0
        extra = claims[k] - base * sales_by[k]
        rows.append(dict(sku=k, product=sk.get("product_description"), shelf_months=sk.get("shelf"), sales=sales_by[k],
                         scheme_stock_value=sch_val[k], free_value=foc_val[k], claims=claims[k], claims_on_scheme_batches=on_scheme[k],
                         claim_rate=rate, extra_cost=extra, extra_cost_per_year=extra * 12 / months))
    rows.sort(key=lambda r: -r["extra_cost"])
    return dict(rows=rows, baseline_rate=base, months=months, total_extra_per_year=sum(r["extra_cost_per_year"] for r in rows),
                note="Expiry (near-expiry and expired) claims, credited and pending, at claim value. Baseline = SKUs that never carry a scheme.")


def foc_by_quarter() -> list[dict]:
    """§4.4: free goods at PTS vs 3% of the quarter's primary sales."""
    tot, foc = defaultdict(float), defaultdict(float)
    for s in sales():
        if s["date"]:
            q = fy_q(s["date"])
            tot[q] += s["net"]
            foc[q] += s["free"] * s["pts"]
    out = [dict(quarter=q, sales=tot[q], free_value=foc[q], share=foc[q] / tot[q], over_cap=foc[q] > C.FOC_CAP * tot[q],
                over_by=max(foc[q] - C.FOC_CAP * tot[q], 0)) for q in sorted(tot)]
    return out


def _by_pair() -> dict:
    if "p" not in _c:
        g = defaultdict(list)
        for s in sales():
            if s["date"]:
                g[(s["stockist"], s["sku"])].append(s)
        _c["p"] = g
    return _c["p"]


def _monthly(stockist: str, sku: str):
    """Paid packs by month for one stockist and SKU, and which months carry a scheme order."""
    paid, sch = defaultdict(float), set()
    for s in _by_pair().get((stockist, sku), []):
        if True:
            m = (s["date"].year, s["date"].month)
            paid[m] += s["paid"]
            if s["scheme"]:
                sch.add(m)
    return paid, sch


def _prev_months(m, n):
    y, mo = m
    for _ in range(n):
        mo -= 1
        if mo == 0:
            y, mo = y - 1, 12
        yield (y, mo)


def screen(stockist: str, sku: str, as_of: date, order_paid: float | None = None) -> dict:
    """Warnings for one stockist and SKU before a scheme: minimum order (1.5 x avg paid month over the 3 months before the scheme),
    and an ESTIMATE of stock on hand against the 2.5-month norm: paid+free packs bought in the 90 days before, less 3 normal months of use.
    The normal month is the median monthly paid purchase over months with no scheme order (Arjun, 20 Nov)."""
    paid, sch = _monthly(stockist, sku)
    m0 = (as_of.year, as_of.month)
    prev = list(_prev_months(m0, C.SCHEME_LOOKBACK_MONTHS))
    avg3 = sum(paid.get(m, 0) for m in prev) / C.SCHEME_LOOKBACK_MONTHS
    normal = sorted(v for m, v in paid.items() if m not in sch and m < m0)
    nm = normal[len(normal) // 2] if normal else 0
    recent = [s for s in _by_pair().get((stockist, sku), []) if 0 < (as_of - s["date"]).days <= 91]
    bought = sum(s["paid"] + s["free"] for s in recent)
    est = max(bought - C.SCHEME_LOOKBACK_MONTHS * nm, 0)
    est_months = est / nm if nm else None
    warns = []
    moq = C.SCHEME_MOQ_MULT * avg3
    if order_paid is not None and avg3 > 0 and order_paid < moq:
        warns.append(f"order {order_paid:.0f} paid packs is below the minimum {moq:.0f} (1.5 x {avg3:.0f}), Annex B")
    if est_months is not None and est_months > C.STOCK_NORM_MONTHS:
        warns.append(f"estimated stock {est_months:.1f} months of a normal month, above {C.STOCK_NORM_MONTHS} (§4.5)")
    if nm == 0:
        warns.append("no non-scheme months on record: normal month unknown, RSM to confirm stock (§4.5)")
    return dict(stockist=stockist, sku=sku, avg_paid_3m=avg3, minimum_order=moq, normal_month=nm, bought_90d=bought,
                est_stock_packs=est, est_stock_months=est_months, warnings=warns,
                evidence=dict(file="primary_sales.csv", rows=[s["row"] for s in recent[:8]], total_rows=len(recent)), blocked=C.SCHEME_BLOCKS and bool(warns),
                label="Stock is an estimate from purchases; no secondary data exists (SSS not received, §4.5 note).")


def scheme_orders(scheme_prefix: str | None = None) -> list[dict]:
    """Historic scheme orders (stockist, SKU, scheme) with the screen run as at the first scheme invoice."""
    g = {}
    for s in sales():
        if s["scheme"] and s["date"] and (scheme_prefix is None or s["scheme"].startswith(scheme_prefix)):
            k = (s["stockist"], s["sku"], s["scheme"])
            e = g.setdefault(k, dict(stockist=k[0], sku=k[1], scheme=k[2], date=s["date"], paid=0.0, free=0.0, cnf=s["cnf"]))
            e["paid"] += s["paid"]
            e["free"] += s["free"]
            e["date"] = min(e["date"], s["date"])
    out = []
    for e in g.values():
        r = screen(e["stockist"], e["sku"], date(e["date"].year, e["date"].month, 1), e["paid"])
        out.append(dict(e, **{k: r[k] for k in ("avg_paid_3m", "minimum_order", "est_stock_months", "warnings")}))
    return out
