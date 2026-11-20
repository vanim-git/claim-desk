# Instructions for the coding agent

Read this file before every task. Keep it short and keep it true.

## What we are building
The **claim desk** for Project Sankalp problem P5. Neha Bansal's Finance team checks expiry and breakage claims
(register rows, new claims typed in, or stockist emails) against policy CO-POL-014 v4.2 before a credit note is issued.
The tool recommends Approve, Reject or Needs a person, with the rule, clause and file row behind each check. A person decides.
It fixes P5 for new claims only; the 373 claims already credited are re-checked by `/api/audit`, not changed.

## Architecture (v2.3, stateless)
Main graph: `intake -> parse_email -> split_lines -> check_line x N (Send) -> explain -> record`.
`check_line` is a compiled subgraph: `validate_claim -> match_register -> gather_facts -> run_checks -> decide`.
- Model nodes (optional): `parse_email`, `explain`. Without `OPENROUTER_API_KEY` they run on regex and a template.
- Plain code: everything else. Rules R1-R8 and D0 are in `agent/rules.py`, limits in `config.py` with page references.
- Injection is detected by code (`agent/parsing.py`), never by the model. A flag forces Needs a person.
- No database, no checkpointer. `/api/decision` only logs; `/api/audit` re-checks credited claims strictly.
- Only `line_results` is shared between the subgraph and the main graph. Keep the other subgraph keys prefixed `l`.

## Rules
- Facts come from `agent/data.py` reading `data/`. The model never writes a batch number, date, quantity or amount.
- Business rules live in `agent/rules.py` with a test in `tests/test_rules.py`; limits in `config.py` with the policy page.
- One small change per task. Run `pytest -q` after each change. Do not touch files the task does not need.
- Do not add a database, a vector store, a new framework or a new folder without asking.
- The frontend stays in `public/` as plain HTML, CSS and JavaScript.
- Secrets live only in `.env` locally and in Vercel environment variables. Never commit them.
- Build paths from `Path(__file__)`. Commit `data/` so it is in the deployed bundle.

## How to run
```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest httpx
pytest -q
uvicorn app:app --reload
```

## Client decisions (answered 20 Nov, see Claude-Output/fde_academy_responses_20nov.md)
A person may reject and the tool recommends Reject with the clause; no-invoice claims pass only with batch invoiced to the stockist + qty within it + written Area Manager approval naming the claim number; batches before the data are escalated, never rejected; boxes need a stated pack size; replies are drafts. Hosted model and Vercel allowed for extract data; no store needed. Still to build: resubmission linking (original claim date).

## Current task
Pilot test on new claims (22 Nov). Done = deployed on Vercel, `/api/health` ok, `pytest -q` green. Next slice: link a resent claim to the first one and judge §5.2 on the original date.
