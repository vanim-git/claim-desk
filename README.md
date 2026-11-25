# Project Sankalp: claim desk (P5)

FastAPI + LangGraph + plain HTML. Checks a claim against CO-POL-014 v4.2 and recommends Approve / Reject / Needs a person, with evidence.
Works with no model key (rules read the email). With a key, a model reads messy emails and words the explanation; it never decides.

```
app.py              routes only: /api/health, /api/claim, /api/decision, /api/audit
config.py           policy limits with page references, and the "person vs reject" defaults
agent/data.py       loads data/*.csv (stdlib csv), cleans them, row numbers as evidence
agent/rules.py      D0 and R1-R8, decide()
agent/parsing.py    regex email parser and injection detector
agent/prompts.py    the two model prompts
agent/graph.py      the LangGraph graph (Send fan-out, check_line subgraph)
agent/llm.py        the only file that knows the model provider (OpenRouter)
data/               sku_master, batch_master, stockist_master, primary_sales, expiry_claims, claim_emails
public/             index.html, app.js, style.css
tests/              pytest, no key needed
```

## Run locally
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest httpx
pytest -q
uvicorn app:app --reload     # http://127.0.0.1:8000
```
Optional: `cp .env.example .env` and add `OPENROUTER_API_KEY` (only once IT approves an outside model).

## Defaults that need the client's answer
| Item | Default | Setting |
|---|---|---|
| Early near-expiry (>90 days) | Recommend Reject; a person decides (Neha, 20 Nov) | `EARLY_NE_ACTION` in config.py |
| Quantity above invoiced + free | Recommend Reject | `QTY_OVER_ACTION` |
| No invoice reference | Needs a person unless batch invoiced to the stockist, qty within it, and written Area Manager approval names the claim | R2 |
| Batch older than the data | Needs a person, never rejected | R1/R2 unknown |
| Decisions and steps | appended to an append-only file (`data/action_log.jsonl`; `/tmp` on Vercel, not durable there); SAP stays the record | `/api/decision`, `/api/action`, `/api/actions` |
| Replies to stockists | draft text only, never sent | none |

Deploy: see `../Claude-Output/vercel_deploy_steps.md`.

## P3 expiry watch (second graph)
the "Expiry watch (P3)" tab (`/#stock`; API: `GET /api/expiry-watch?viewer=all|CF-E01&as_of=YYYY-MM-DD`). Code: `agent/stock.py` (rules), `agent/stock_graph.py` (one `check_cnf` run per C&F via `Send`, then pick list and §7.1 breach list). Thresholds in `config.py` (60% floor, 70% warning, 2 months buffer, flag-not-block). Data: `data/cnf_stock_snapshot.csv`. No model, nothing stored. Tests: `tests/test_stock.py`.

## P2 and P1
the "Scheme desk (P2)" tab (`/#schemes`; `GET /api/scheme-desk`; `agent/schemes.py`, `schemes_graph.py`) and the "Supply desk (P1)" tab (`/#supply`; `GET /api/supply-desk`; `agent/supply.py`, `supply_graph.py`). Limits in `config.py`. No model, nothing stored, proposals only. Tests: `tests/test_schemes.py`, `tests/test_supply.py` (73 in all).

## Added 25 Nov: digest, sources, data log, outward
- Tab "Weekly digest" (`/#digest`, `GET /api/digest`): one section per owner, read-only, nothing stored or sent (`agent/digest.py`). `GET /api/data-log` counts the fixes made while loading the raw CSVs.
- P1-P3 results carry `evidence` (source rows) and the pages show a Source column.
- Outward (monthly sales out of a C&F) is taken from invoices: median of the last six months of paid packs (`config.OUTWARD_FROM_INVOICES`, `OUTWARD_MONTHS`). The snapshot's `avg_monthly_outward_packs` runs at about 0.35 of that and is only a fallback. 83 tests.
- **Action log** (`agent/actionlog.py`): append-only, hash-chained, one line per step a person took ("return requested", "move approved", claim decisions). `POST /api/action`, `GET /api/actions`; form on the Weekly digest tab. Where: `ACTION_LOG` env var, else `data/action_log.jsonl` (git-ignored), else `/tmp` on Vercel, where it is **lost on a cold start**: a hosted store is still needed for real use. No sign-in yet, so the name is typed. Tests never touch the real file (`tests/conftest.py`). 89 tests.
- Outward from invoices is final (the user confirmed 25 Nov); React and pandas are not used.
