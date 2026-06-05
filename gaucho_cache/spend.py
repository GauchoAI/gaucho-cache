"""Spend ledger: every Cerebras call records its ACTUAL token usage.

The pricing chapter (99-pricing.md) reports real dollars from this
ledger, not estimates — the same discipline the medical-codes repo
applies to its cost analysis. Append-only JSONL at data/spend_ledger.jsonl:

    {"ts": ..., "activity": "traffic_sim", "model": "gpt-oss-120b",
     "input_tokens": 1812, "output_tokens": 970, "usd": 0.001362}

A hard budget guard stops the campaign before the cap: any record that
would push the cumulative total past BUDGET_USD raises BudgetExceeded.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LEDGER = REPO / "data" / "spend_ledger.jsonl"

# Cerebras gpt-oss-120b list prices (USD per 1M tokens).
PRICE_IN = 0.35
PRICE_OUT = 0.75

BUDGET_USD = 95.0   # hard stop with margin under the $100 directive

_lock = threading.Lock()


class BudgetExceeded(RuntimeError):
    pass


def cost(input_tokens: int, output_tokens: int) -> float:
    return input_tokens * PRICE_IN / 1e6 + output_tokens * PRICE_OUT / 1e6


def record(activity: str, input_tokens: int, output_tokens: int,
           model: str = "gpt-oss-120b") -> float:
    """Append one usage record; returns its cost. Raises BudgetExceeded
    once the cumulative ledger would pass BUDGET_USD."""
    usd = cost(input_tokens, output_tokens)
    with _lock:
        total = spent() + usd
        if total > BUDGET_USD:
            raise BudgetExceeded(
                f"ledger at ${spent():.2f}; +${usd:.4f} would exceed "
                f"${BUDGET_USD}")
        LEDGER.parent.mkdir(exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": round(time.time(), 1), "activity": activity,
                "model": model, "input_tokens": input_tokens,
                "output_tokens": output_tokens, "usd": round(usd, 6),
            }) + "\n")
    return usd


def _rows() -> list[dict]:
    if not LEDGER.exists():
        return []
    return [json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip()]


def spent() -> float:
    return sum(r["usd"] for r in _rows())


def summary() -> dict[str, dict]:
    """Per-activity totals: calls, tokens, usd."""
    out: dict[str, dict] = {}
    for r in _rows():
        a = out.setdefault(r["activity"], {"calls": 0, "input_tokens": 0,
                                           "output_tokens": 0, "usd": 0.0})
        a["calls"] += 1
        a["input_tokens"] += r["input_tokens"]
        a["output_tokens"] += r["output_tokens"]
        a["usd"] += r["usd"]
    for a in out.values():
        a["usd"] = round(a["usd"], 4)
    return out
