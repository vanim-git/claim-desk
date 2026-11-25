"""Append-only action log: the steps people take on the desks ("return requested", "move approved", a claim decision).

One JSON line per step, written with append only; nothing is edited or deleted by this code. Each line carries the hash of the
line before it, so a changed or removed line is detected by `verify()`. No database: a plain file.
Where it lives: `ACTION_LOG` env var, else `data/action_log.jsonl` on a laptop, else `/tmp/sankalp_action_log.jsonl` on Vercel.
Vercel keeps no disk between instances, so there the log is NOT durable (it is lost on a cold start): it needs a hosted store
before real use. The answer says so (`durable`)."""
import fcntl
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

STEPS = {
    "claim": ("decision accepted", "decision overridden"),
    "stock": ("return requested", "pick list sent", "sent to CDC", "sold first", "stockist agreed to short-dated stock", "no action"),
    "schemes": ("RSM warned", "stockist left out of scheme", "no action"),
    "supply": ("move approved", "move declined", "share change approved", "share change declined"),
}
GENESIS = "0" * 64


def path() -> Path:
    if os.getenv("ACTION_LOG"):
        return Path(os.environ["ACTION_LOG"])
    if os.getenv("VERCEL"):
        return Path("/tmp/sankalp_action_log.jsonl")
    return Path(__file__).resolve().parent.parent / "data" / "action_log.jsonl"


def durable() -> bool:
    return not os.getenv("VERCEL") or bool(os.getenv("ACTION_LOG"))


def _hash(prev: str, body: dict) -> str:
    return hashlib.sha256((prev + json.dumps(body, sort_keys=True, ensure_ascii=False)).encode()).hexdigest()


def _lines(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def append(desk: str, step: str, by: str, ref: str = "", note: str = "") -> dict:
    """Add one step. Raises ValueError for a desk or step that is not allowed or a missing name (no sign-in yet, so `by` is typed)."""
    if desk not in STEPS or step not in STEPS[desk]:
        raise ValueError(f"step must be one of {list(STEPS.get(desk, ()))} for desk '{desk}'")
    if not (by or "").strip():
        raise ValueError("say who took the step (no sign-in yet)")
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a+", encoding="utf-8") as f:
        fcntl.flock(f, fcntl.LOCK_EX)          # two requests at once must not take the same sequence number
        f.seek(0)
        last = [json.loads(x) for x in f.read().splitlines() if x.strip()][-1:]
        prev, seq = (last[0]["hash"], last[0]["seq"] + 1) if last else (GENESIS, 1)
        body = dict(seq=seq, at=datetime.now(timezone.utc).isoformat(timespec="seconds"), desk=desk, step=step,
                    ref=(ref or "").strip(), by=by.strip(), note=(note or "").strip(), prev=prev)
        entry = dict(body, hash=_hash(prev, body))
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    return entry


def read(limit: int = 100, desk: str | None = None) -> list[dict]:
    rows = [r for r in _lines(path()) if desk in (None, r["desk"])]
    return rows[-limit:][::-1]


def verify() -> dict:
    """Walk the chain from the first line. `ok` is False at the first line whose hash or link does not match."""
    prev, n = GENESIS, 0
    for r in _lines(path()):
        body = {k: v for k, v in r.items() if k != "hash"}
        if r["prev"] != prev or r["hash"] != _hash(prev, body) or r["seq"] != n + 1:
            return dict(ok=False, entries=n, broken_at=r.get("seq"))
        prev, n = r["hash"], n + 1
    return dict(ok=True, entries=n, broken_at=None)
