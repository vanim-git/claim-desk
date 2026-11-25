"""Loads the CSVs once and cleans them with the same rules as the analysis (clean.py).

Plain stdlib `csv`, no pandas: it keeps the Vercel bundle small and loads in well under a second.
`row` is the 1-based data row in the raw file (file line = row + 1), used as evidence.
Cleaning: three date formats, upper-cased codes, PFL-1301 -> PFL1301, CFE01 -> CF-E01,
INV-... -> INV/..., comma numbers, exact duplicate rows dropped before and after normalising.
"""
import csv
import re
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def to_date(s) -> date | None:
    s = (s or "").strip()
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d-%b-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def to_num(s) -> float | None:
    try:
        return float(str(s).replace(",", "").strip())
    except ValueError:
        return None


def code(s) -> str:
    return (s or "").strip().upper()


def norm_invoice(s) -> str | None:
    s = (s or "").strip()
    return re.sub(r"^INV-", "INV/", s) or None


def _rows(name: str) -> list[dict]:
    with open(DATA / f"{name}.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for i, r in enumerate(rows, 1):
        r["row"] = i
    return rows


def _dedup(rows: list[dict], key) -> list[dict]:
    seen, out = set(), []
    for r in rows:
        k = key(r)
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out


def _raw(r):
    return tuple(v for k, v in r.items() if k != "row")


class Data:
    def __init__(self):
        self.sku = {code(r["sku_code"]): dict(r, pts=to_num(r["pts_inr"]), shelf=to_num(r["shelf_life_months"]))
                    for r in _rows("sku_master")}
        self.batch = {}
        for r in _rows("batch_master"):
            self.batch.setdefault(code(r["batch_no"]), dict(r, sku=code(r["sku_code"]), expiry=to_date(r["expiry_date"])))
        self.stockist = {code(r["stockist_code"]): dict(r, cnf=r["cnf_code"].strip()) for r in _rows("stockist_master")}

        # sales: exact duplicates dropped before and after normalising
        ps = _dedup(_rows("primary_sales"), _raw)
        self.lines, self.invoice, self.sold_batches = {}, {}, set()
        seen = set()
        for r in ps:
            n = dict(invoice_no=r["invoice_no"].strip(), date=to_date(r["invoice_date"]), cnf=r["cnf_code"].strip(),
                     stockist=code(r["stockist_code"]), sku=code(r["sku_code"]), batch=code(r["batch_no"]) or None,
                     packs=(to_num(r["invoiced_qty"]) or 0) + (to_num(r["free_qty"]) or 0), row=r["row"])
            k = tuple(v for kk, v in n.items() if kk != "row")
            if k in seen:
                continue
            seen.add(k)
            inv = self.invoice.setdefault(n["invoice_no"], dict(date=n["date"], stockist=n["stockist"], cnf=n["cnf"],
                                                                batches=set(), row=n["row"]))
            if n["batch"]:
                inv["batches"].add(n["batch"])
                self.sold_batches.add(n["batch"])
                self.lines.setdefault((n["stockist"], n["batch"]), []).append(n)

        # register claims
        ec = _dedup(_rows("expiry_claims"), _raw)
        self.claims, self.by_key, self.by_no, self.rejected = [], {}, {}, {}
        seen = set()
        for r in ec:
            c = dict(claim_no=r["claim_no"].strip(), claim_date=to_date(r["claim_date"]), stockist=code(r["stockist_code"]),
                     cnf=r["cnf_code"].strip(), sku=code(r["sku_code"]).replace("-", ""), batch=code(r["batch_no"]),
                     stated_expiry=to_date(r["expiry_date_as_claimed"]), qty=to_num(r["qty_claimed"]),
                     value=to_num(r["claim_value_inr"]), claim_type=r["claim_type"].strip(), invoice_ref=norm_invoice(r["original_invoice_ref"]),
                     status=r["status"].strip(), cn_no=r["credit_note_no"].strip() or None,
                     credit_value=to_num(r["credit_value_inr"]), row=r["row"])
            k = tuple(v for kk, v in c.items() if kk != "row")
            if k in seen:
                continue
            seen.add(k)
            self.claims.append(c)
            self.by_no[c["claim_no"]] = c
            if c["status"] == "Rejected":
                self.rejected.setdefault((c["stockist"], c["batch"]), []).append(c)
            if c["status"] in ("Credited", "Pending"):
                self.by_key.setdefault((c["stockist"], c["batch"]), []).append(c)
        self.claimed_batches = {c["batch"] for c in self.claims}
        self.emails = {r["email_id"]: dict(r, stockist=code(r["stockist_code_by_mailbox_rule"]) or None,
                                           received=to_date(r["received_date"])) for r in _rows("claim_emails")}


@lru_cache(maxsize=1)
def get() -> Data:
    return Data()


# ---- typed lookups used by the graph --------------------------------------------------------
def batch_known(batch_no: str) -> bool:
    d = get()
    return batch_no in d.batch or batch_no in d.sold_batches or batch_no in d.claimed_batches


def expiry_for(batch_no: str, stated: date | None = None):
    """Expiry date and where it came from: batch master, then the expiry the claim itself states, then earlier register claims on that batch."""
    d = get()
    if batch_no in d.batch and d.batch[batch_no]["expiry"]:
        return d.batch[batch_no]["expiry"], {"file": "batch_master.csv", "row": d.batch[batch_no]["row"]}
    if stated:
        return stated, {"file": "claim text", "note": "batch not in batch master: the expiry the claim states"}
    for c in d.claims:
        if c["batch"] == batch_no and c["stated_expiry"]:
            return c["stated_expiry"], {"file": "expiry_claims.csv", "row": c["row"], "note": "batch not in batch master"}
    return None, None


def sku_for(batch_no: str) -> str | None:
    d = get()
    if batch_no in d.batch:
        return d.batch[batch_no]["sku"]
    for c in d.claims:
        if c["batch"] == batch_no:
            return c["sku"]
    return None


def supplied(stockist: str, batch_no: str, as_of: date | None = None):
    """Packs invoiced plus free to this stockist for this batch (up to `as_of`), and the rows."""
    rows = get().lines.get((stockist, batch_no), [])
    if as_of:
        rows = [r for r in rows if r["date"] and r["date"] <= as_of]
    return sum(r["packs"] for r in rows), rows


def prior_claims(stockist: str, batch_no: str, claim_date: date, exclude_claim_no: str | None = None):
    """Earlier credited or pending register claims on the same stockist and batch."""
    return [c for c in get().by_key.get((stockist, batch_no), [])
            if c["claim_no"] != exclude_claim_no and c["claim_date"] and c["claim_date"] <= claim_date]


def typo_candidates(batch_no: str) -> list[str]:
    """Known batches that differ only by letter O vs zero (OCR-style typo)."""
    d = get()
    fixed = batch_no[:1] + batch_no[1:].replace("O", "0")
    known = set(d.batch) | d.sold_batches | d.claimed_batches
    return [fixed] if fixed != batch_no and fixed in known else []


# ---- fix log ---------------------------------------------------------------------------------------
def cleaning_log() -> dict:
    """What the loader changes, counted per file, so no fix is silent. Raw files are never edited; this re-reads them and counts
    exact duplicate rows (dropped), dates not written dd-mm-yyyy (parsed), SKU codes with a hyphen, C&F codes without one,
    invoice numbers written INV-, numbers with commas, and blank batch numbers (kept, but they cannot be matched to a batch)."""
    files = {}
    for path in sorted(DATA.glob("*.csv")):
        rows = _rows(path.stem)
        cols = [c for c in rows[0] if c != "row"] if rows else []
        seen, dups = set(), 0
        for r in rows:
            k = _raw(r)
            dups += k in seen
            seen.add(k)
        v = lambda c: [(r.get(c) or "").strip() for r in rows]
        fx = {}
        date_cols = [c for c in cols if "date" in c]
        n = sum(1 for c in date_cols for x in v(c) if x and not re.fullmatch(r"\d{2}-\d{2}-\d{4}", x))
        if n:
            fx["dates_in_other_formats"] = n
        n = sum(1 for c in cols if c.startswith("sku") for x in v(c) if "-" in x)
        if n:
            fx["sku_codes_with_hyphen"] = n
        n = sum(1 for c in cols if c.startswith("cnf") for x in v(c) if re.fullmatch(r"[A-Za-z]{2}\d{2,3}", x))
        if n:
            fx["cnf_codes_without_hyphen"] = n
        n = sum(1 for c in cols if "invoice" in c for x in v(c) if x.startswith("INV-"))
        if n:
            fx["invoice_numbers_written_INV-"] = n
        n = sum(1 for c in cols for x in v(c) if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", x))
        if n:
            fx["numbers_with_commas"] = n
        n = sum(1 for c in cols if c.startswith("batch") for x in v(c) if not x)
        if n:
            fx["blank_batch_numbers"] = n
        files[path.name] = dict(rows=len(rows), exact_duplicate_rows_dropped=dups, **fx)
    return dict(files=files, note="Raw files are never edited. Fixes are applied when the data is loaded (agent/data.py); this log counts them.")
