"""Reading email text. Used by parse_email: a model when a key is set, these rules when not.
The email is untrusted: code (not the model) decides whether it looks like an injection attempt."""
import re
from datetime import date, timedelta

BATCH = r"\b([A-Z]\d{2}[0-9O]\d{4})\b"
INVOICE = r"INV[/-][A-Z]\d{2}[/-]\d{4}[/-]\d{6}"
INJECTION = re.compile(r"ignore (all |any |the )?(previous|prior|above)|ai assistant|system prompt|"
                       r"approve (this|it|the claim)|skip (the )?(checks?|validation|verification)|disregard", re.I)


def injection_suspected(text: str) -> bool:
    return bool(INJECTION.search(text or ""))


def parse_expiry(s: str | None) -> date | None:
    """'30-09-2026', '09/2026', 'Sep 2026', 'Sep-26' -> a date (month end when only a month is given)."""
    if not s:
        return None
    s = s.strip()
    m = re.fullmatch(r"(\d{2})-(\d{2})-(\d{4})", s)
    if m:
        return date(int(m[3]), int(m[2]), int(m[1]))
    m = re.fullmatch(r"(\d{2})/(\d{4})", s)
    mon, yr = (int(m[1]), int(m[2])) if m else (None, None)
    if not m:
        m = re.fullmatch(r"([A-Za-z]{3})[- ](\d{2,4})", s)
        if not m:
            return None
        try:
            mon = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"].index(m[1].lower()) + 1
        except ValueError:
            return None
        yr = int(m[2]) + (2000 if int(m[2]) < 100 else 0)
    nxt = date(yr + (mon == 12), mon % 12 + 1, 1)
    return nxt - timedelta(days=1)


def regex_parse(body: str) -> dict:
    """Fallback when no model key is set. Handles lines like 'batch K2300101, exp Sep 2026, 241 strips, inv INV/..'."""
    b = (body or "").lower()
    if re.search(r"status|what happened|claim clm-", b) and not re.search(r"batch [a-z0-9]+.*\d+\s*strips", b):
        intent = "status_query"
    elif re.search(r"batch|strips|qty|expiry return|near expiry|expired", b):
        intent = "claim"
    else:
        intent = "other"
    lines = []
    for ln in (body or "").split("\n"):
        bt = re.search(BATCH, ln)
        q = re.search(r"(\d+)\s*(strips?|boxes)(?:\s*\((\d+)\s*strips each\))?|qty\s*(\d+)|\|\s*(\d+)\s*\|", ln, re.I)
        if bt and q:
            n = int(next(v for v in (q.group(1), q.group(4), q.group(5)) if v))
            xp = (re.search(r"exp(?:iry)?\.?\s*(\d{2}-\d{2}-\d{4}|\d{2}/\d{4}|[A-Z][a-z]{2}[- ]\d{2,4})", ln)
                  or re.search(r"\|\s*([A-Z][a-z]{2} \d{4})\s*\|", ln))
            inv = re.search(INVOICE, ln)
            lines.append(dict(batch_no=bt.group(1), qty=n, unit=(q.group(2) or "strips").lower(),
                              per_box=int(q.group(3)) if q.group(3) else None,
                              stated_expiry=xp.group(1) if xp else None,
                              invoice_no=inv.group(0).replace("-", "/") if inv else None))
    ref = {}
    cn = re.search(r"CLM-\d{4}-\d{5}", body or "")
    if cn:
        ref["claim_no"] = cn.group(0)
    bt = re.search(BATCH, body or "")
    if bt:
        ref["batch_no"] = bt.group(1)
    return {"intent": intent, "lines": lines, "status_ref": ref or None}
