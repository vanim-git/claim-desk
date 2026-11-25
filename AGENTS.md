# Instructions for the coding agent

Read this file before every task. Keep it short and keep it true.

## What we are building
The **claim desk** for Project Sankalp problem P5. Neha Bansal's Finance team checks expiry and breakage claims
(register rows, new claims typed in, or stockist emails) against policy CO-POL-014 v4.2 before a credit note is issued.
The tool recommends Approve, Reject or Needs a person, with the rule, clause and file row behind each check. A person decides.
It fixes P5 for new claims only; the 373 claims already credited are re-checked by `/api/audit`, not changed.

## Architecture (v2.3; the graph is stateless, steps go to an append-only file)
Main graph: `intake -> parse_email -> split_lines -> check_line x N (Send) -> explain -> record`.
`check_line` is a compiled subgraph: `validate_claim -> match_register -> gather_facts -> run_checks -> decide`.
- Model nodes (optional): `parse_email`, `explain`. Without `OPENROUTER_API_KEY` they run on regex and a template.
- Plain code: everything else. Rules R1-R8 and D0 are in `agent/rules.py`, limits in `config.py` with page references.
- Injection is detected by code (`agent/parsing.py`), never by the model. A flag forces Needs a person.
- No database, no checkpointer. `/api/decision` adds the decision to the append-only action log (`agent/actionlog.py`: one JSON line per step, each line carries the hash of the one before, `GET /api/actions` checks the chain); `/api/audit` re-checks credited claims strictly.
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

## P3 (expiry watch)
Rules live in `agent/stock.py`; the graph in `agent/stock_graph.py`; limits in `config.py`. Breaches are flagged, never blocked (`BLOCK_BELOW_FLOOR = False`). RDM names are only known for CF-E01; add others in `config.RDM` when Kavita confirms.

## P2 and P1
Rules in `agent/schemes.py` and `agent/supply.py`, graphs in `agent/schemes_graph.py` and `agent/supply_graph.py`. Load shared data in the `plan` node before any `Send` fan-out. Warn, never block (`SCHEME_BLOCKS = False`). Moves and share changes are proposals for Kavita Rao.

## Added 25 Nov: digest, sources, data log, outward
- Tab "Weekly digest" (`/#digest`, `GET /api/digest`): one section per owner, read-only, nothing stored or sent (`agent/digest.py`). `GET /api/data-log` counts the fixes made while loading the raw CSVs.
- P1-P3 results carry `evidence` (source rows) and the pages show a Source column.
- Outward (monthly sales out of a C&F) is taken from invoices: median of the last six months of paid packs (`config.OUTWARD_FROM_INVOICES`, `OUTWARD_MONTHS`). The snapshot's `avg_monthly_outward_packs` runs at about 0.35 of that and is only a fallback. 83 tests.
- **Action log** (`agent/actionlog.py`): append-only, hash-chained, one line per step a person took ("return requested", "move approved", claim decisions). `POST /api/action`, `GET /api/actions`; form on the Weekly digest tab. Where: `ACTION_LOG` env var, else `data/action_log.jsonl` (git-ignored), else `/tmp` on Vercel, where it is **lost on a cold start**: a hosted store is still needed for real use. No sign-in yet, so the name is typed. Tests never touch the real file (`tests/conftest.py`). 89 tests.
- Outward from invoices is final (the user confirmed 25 Nov); React and pandas are not used.
