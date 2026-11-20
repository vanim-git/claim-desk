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
    """The person's decision. An override needs a reason. It is written to the log only: nothing is stored."""
    if body.action == "override" and not (body.reason or "").strip():
        return JSONResponse({"error": "An override needs a reason"}, status_code=422)
    print(json.dumps({"decision": body.model_dump()}), flush=True)
    return {"recorded": True, "note": "Written to the function log only. Nothing is stored."}


@app.get("/api/audit")
def audit():
    """Re-check every credited claim in strict mode: the money already paid against the rules."""
    return audit_credited()


@app.get("/")
def index():
    return FileResponse(ROOT / "public" / "index.html")


# On Vercel the public/ folder is served by the platform. On a laptop nothing serves it, so mount it only then.
if not os.getenv("VERCEL"):
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory=ROOT / "public"), name="public")
