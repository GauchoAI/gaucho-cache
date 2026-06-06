#!/usr/bin/env python3
"""Re-audit closure-ingested positives against the template-fit standard.

The first closure campaign (2026-06-06) ingested unheard answers under a
label-only judge. The template-fit refinement showed some of those labels
are serving traps: "Sí, pasame a la gente, porfa" filed under confirmation
would serve a generic proceed-ack to someone asking for a human. This
script runs every register='closure' row through the same two-step verdict
new ingestions face (intent label + would-this-template-fit) and drops the
rows that fail (dropped=1, never deleted — the ledger keeps receipts).

Usage: CEREBRAS_API_KEY=... uv run python scripts/reaudit_closure_rows.py
"""
from __future__ import annotations

import asyncio
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from close_question_coverage import FIT_PROMPT, FIT_SYS
from gaucho_cache import spend
from gaucho_cache.cerebras import BatchClient
from gaucho_cache.contracts import load_all_contracts

DB_PATH = REPO / "data" / "slice.sqlite"


async def main() -> None:
    contracts = load_all_contracts(REPO, REPO / "data/contract_extensions.yaml")
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        "SELECT id, intent, text FROM variants "
        "WHERE register='closure' AND dropped=0 AND kind='positive'").fetchall()
    print(f"{len(rows)} closure rows to re-audit")
    client = BatchClient("closure_reaudit")

    async def fit(row_id: int, intent: str, text: str):
        c = contracts.get(intent)
        if c is None:
            return row_id, intent, text, False
        v = await client.chat_json(
            FIT_SYS, FIT_PROMPT.format(
                answer=text, question="(una pregunta del bot en el funnel)",
                template=c.body), temperature=0.0)
        ok = isinstance(v, dict) and v.get("verdict") == "ok"
        return row_id, intent, text, ok

    verdicts = await asyncio.gather(*(fit(*r) for r in rows))
    bad = [(rid, i, t) for rid, i, t, ok in verdicts if not ok]
    for rid, i, t in bad:
        print(f"  dropping [{i}] {t!r}")
    if bad:
        con.executemany("UPDATE variants SET dropped=1 WHERE id=?",
                        [(rid,) for rid, _, _ in bad])
        con.commit()
    con.close()
    print(f"\n{len(bad)}/{len(rows)} closure rows dropped as serving traps; "
          f"ledger ${spend.spent():.2f}")


if __name__ == "__main__":
    asyncio.run(main())
