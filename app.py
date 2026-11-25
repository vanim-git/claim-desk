"""FastAPI entrypoint: routes only, no logic. Vercel finds the instance named `app`.

Run locally:   uvicorn app:app --reload        then open http://127.0.0.1:8000
On Vercel:     public/ is served from the CDN; /api/* reaches this app.
"""
import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from agent import actionlog
from agent.schemes_graph import run_schemes
from agent.supply_graph import run_supply
from agent.stock_graph import run_watch
from agent.graph import audit_credited, llm_available, run_claim

app = FastAPI(title="Project Sankalp claim desk")
ROOT = Path(__file__).resolve().parent


class NewClaim(BaseModel):
    stockist_code: str
    batch_no: str
    qty: float
    claim_type: str | None = None       # Near expiry | Expired | Breakage in transit | Short supply
    claim_date: str | None = None       # dd-mm-yyyy or yyyy-mm-dd; today if blank
    invoice_ref: str | None = None
    resubmission_of: str | None = None  # claim number of the first claim, if this is a resend
    am_approval: str | None = None      # text of the written Area Manager approval; must name the claim number


class ClaimRequest(BaseModel):
    claim_no: str | None = None         # a claim already in the register
    claim: NewClaim | None = None       # a new claim typed into the form
    email_id: str | None = None         # an email in the sample mailbox
    email_text: str | None = None       # pasted email text
    sender: str | None = None           # stockist code of the sender
    received: str | None = None


class Decision(BaseModel):
    claim_ref: str
    line_no: int = 1
    recommended: str
    action: str                         # accept | override
    reason: str | None = None
    reviewer: str | None = None


@app.get("/api/health")
def health():
    """Quick check that the deployment is alive. The key is optional: without it emails are read by rules."""
    return {"ok": True, "model_key_set": llm_available()}


@app.post("/api/claim")
def claim(body: ClaimRequest):
    """Run one claim (or one email with several lines) through the graph and return a recommendation per line."""
    if not (body.claim_no or body.claim or body.email_id or body.email_text):
        return JSONResponse({"error": "Give a claim number, a new claim, an email id or email text"}, status_code=422)
    try:
        return jsonable_encoder(run_claim(body.model_dump(exclude_none=True)))
    except ValueError as err:  # e.g. missing model key
        return JSONResponse({"error": str(err)}, status_code=503)


@app.post("/api/decision")
def decision(body: Decision):
    """The person's decision. An override needs a reason. It is added to the append-only action log (and the function log)."""
    if body.action == "override" and not (body.reason or "").strip():
        return JSONResponse({"error": "An override needs a reason"}, status_code=422)
    print(json.dumps({"decision": body.model_dump()}), flush=True)
    try:
        e = actionlog.append("claim", "decision accepted" if body.action == "accept" else "decision overridden", body.reviewer or "unnamed reviewer",
                             ref=f"{body.claim_ref} line {body.line_no}", note=f"recommended {body.recommended}" + (f"; {body.reason}" if body.reason else ""))
        return {"recorded": True, "seq": e["seq"], "durable": actionlog.durable(),
                "note": "Added to the append-only action log." + ("" if actionlog.durable() else " On Vercel this file is lost on a cold start: not durable.")}
    except OSError as err:   # the disk is read-only or full: the decision still shows in the function log above
        return {"recorded": False, "note": f"Action log not writable ({err.__class__.__name__}); written to the function log only."}


@app.get("/api/audit")
def audit():
    """Re-check every credited claim in strict mode: the money already paid against the rules."""
    return audit_credited()


@app.get("/api/expiry-watch")
def expiry_watch(viewer: str = "all", as_of: str | None = None):
    """P3 weekly early warning. viewer = 'all' (Supply Chain head) or one C&F code (that region's RDM)."""
    from datetime import date
    try:
        d = date.fromisoformat(as_of) if as_of else None
    except ValueError:
        return JSONResponse({"error": "as_of must be YYYY-MM-DD"}, status_code=422)
    return JSONResponse(jsonable_encoder(run_watch(viewer, d)))


@app.get("/api/scheme-desk")
def scheme_desk(as_of: str | None = None):
    """P2: per-SKU scheme stock vs expiry claims, free-goods cap by quarter, and stockists whose estimated stock is above 2.5 months."""
    from datetime import date
    try:
        d = date.fromisoformat(as_of) if as_of else None
    except ValueError:
        return JSONResponse({"error": "as_of must be YYYY-MM-DD"}, status_code=422)
    return JSONResponse(jsonable_encoder(run_schemes(d)))


@app.get("/api/supply-desk")
def supply_desk():
    """P1: unfilled orders, allocation shares vs current, and proposed moves of spare stock through the CDC."""
    return JSONResponse(jsonable_encoder(run_supply()))


class Step(BaseModel):
    desk: str                           # claim | stock | schemes | supply
    step: str                           # one of actionlog.STEPS[desk]
    by: str
    ref: str = ""                       # what it is about: a batch, SKU, stockist, move or claim number
    note: str = ""


@app.post("/api/action")
def record_action(body: Step):
    """Record a step a person took on a desk. Append-only; the tool never takes the step itself."""
    try:
        e = actionlog.append(body.desk, body.step, body.by, body.ref, body.note)
    except ValueError as err:
        return JSONResponse({"error": str(err)}, status_code=422)
    except OSError as err:
        return JSONResponse({"error": f"action log not writable: {err.__class__.__name__}"}, status_code=503)
    return {"recorded": True, "entry": e, "durable": actionlog.durable()}


@app.get("/api/actions")
def actions(limit: int = 100, desk: str | None = None):
    """The latest steps first, with a check that the chain is unbroken, and the allowed steps per desk."""
    return {"entries": actionlog.read(max(1, min(limit, 500)), desk), "chain": actionlog.verify(), "durable": actionlog.durable(),
            "steps": actionlog.STEPS}


@app.get("/api/digest")
def digest_api():
    """Weekly digest: one section per owner, built from the P1-P3 results. Read-only; nothing is stored or sent."""
    from agent.digest import build_digest
    return JSONResponse(jsonable_encoder(build_digest()))


@app.get("/api/data-log")
def data_log():
    """What the loader fixes in the raw extracts, counted per file (raw files are never edited)."""
    from agent.data import cleaning_log
    return JSONResponse(jsonable_encoder(cleaning_log()))


@app.get("/")
def index():
    return FileResponse(ROOT / "public" / "index.html")


# On Vercel the public/ folder is served by the platform. On a laptop nothing serves it, so mount it only then.
if not os.getenv("VERCEL"):
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=ROOT / "public"), name="public")
