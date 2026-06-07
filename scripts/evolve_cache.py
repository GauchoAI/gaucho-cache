#!/usr/bin/env python3
"""The flywheel: compact → re-gate → report triggers. One ledgered pass.

This is the maintenance cron the cache runs on itself. Compaction is
local and free; the gates that follow cost nothing (no LLM); only the
triggers a human/agent chooses to act on spend money. A pass NEVER
ships a corpus that fails its gates — if compaction somehow moved a
serving boundary, eval/probes catch it and the pass aborts before
rebuild is trusted.

Usage:
  uv run python scripts/evolve_cache.py            # dry run (report only)
  uv run python scripts/evolve_cache.py --apply    # compact + rebuild + gate
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from gaucho_cache.evolution import (annotate, compact, rollback_compaction,
                                    triggers)


def run(script: str, *args: str) -> str:
    r = subprocess.run([sys.executable, str(REPO / "scripts" / script), *args],
                       capture_output=True, text=True)
    return r.stdout + r.stderr


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="actually tombstone + rebuild + gate (default: dry)")
    a = ap.parse_args()

    if not a.apply:
        # dry run: measure the duplicate mass without touching anything
        import sqlite3
        from collections import defaultdict
        import numpy as np
        from gaucho_cache.classifier import Embedder
        con = sqlite3.connect(REPO / "data" / "slice.sqlite")
        rows = con.execute("SELECT intent, text, register FROM variants WHERE "
                           "stage='objection' AND kind='positive' AND "
                           "dropped=0").fetchall()
        vecs = Embedder().encode([r[1] for r in rows])
        by = defaultdict(list)
        for i, r in enumerate(rows):
            by[r[0]].append(i)
        dup = 0
        for intent, idxs in by.items():
            kept = []
            for i in idxs:
                if rows[i][2] == "curated":
                    kept.append(i); continue
                if any(float(vecs[i] @ vecs[k]) >= 0.97 for k in kept):
                    dup += 1
                else:
                    kept.append(i)
        print(f"DRY RUN: {len(rows)} active positives | "
              f"{dup} near-duplicates ({dup/max(1,len(rows)):.0%}) "
              f"compactable → {len(rows)-dup} after")
        print("\nsample annotations:")
        for blk in annotate(limit=3):
            print("  " + blk.replace("\n", "\n  ").rstrip())
        tg = triggers()
        print(f"\ntraining triggers from proxy traffic: {len(tg)} "
              f"neighbourhood(s)")
        for c in tg[:5]:
            print(f"  ×{c['size']}  {c['exemplar'][:70]!r}")
        return

    rep = compact()
    print(f"COMPACTED: {rep.before} → {rep.after} active "
          f"({rep.merged} merged)")
    for i, n in sorted(rep.by_intent.items(), key=lambda kv: -kv[1])[:8]:
        print(f"  {i}: -{n}")

    print("\nre-gating (compaction must not move a serving boundary):")
    out = run("build_index.py")
    print("  " + next((l for l in out.splitlines() if "wrote" in l), "?")[:80])
    ev = run("eval_slice.py")
    gate = next((l for l in ev.splitlines() if "Gate" in l), "?")
    cw = next((l for l in ev.splitlines() if "Confident-wrong" in l), "?")
    print(f"  {cw.strip()}\n  {gate.strip()}")
    pr = run("probe_conversation.py")
    print(f"  probes: {next((l for l in pr.splitlines() if 'gate' in l), '?').strip()}")
    if "FAIL" in ev or "REGRESS" in pr:
        n = rollback_compaction()
        run("build_index.py")        # restore the gate-green index
        print(f"\n✗ compaction moved a boundary — AUTO-ROLLED BACK "
              f"({n} rows restored, index rebuilt). Corpus left gate-green.")
        sys.exit(1)
    print("\n✓ flywheel pass clean")
    tg = triggers()
    if tg:
        print(f"\n{len(tg)} training trigger(s) queued (act with distill):")
        for c in tg[:5]:
            print(f"  ×{c['size']}  {c['exemplar'][:70]!r}")


if __name__ == "__main__":
    main()
