#!/usr/bin/env python3
"""The domain pipeline: plug into any domain, converge automatically.

One command runs the whole certification loop the chapters built by
hand. Per round, the situation matrix (fresh 10×10 probes, medical
density) measures the domain; its failures feed BOTH ratchets —
FNs (missed true-probes, labeled by construction) become positives,
FPs (impostor serves) become negatives — thresholds recalibrate, and
the loop repeats until convergence:

  CERTIFIED   FP == 0  AND  recall >= target
  WITHHELD    max rounds reached — stays in shadow-serve

Works on both kinds of domain:
  --domain <pack>   a traffic-distilled pack (data/domains/<pack>)
  (no flag)         the hand-built mattress slice (sqlite + full gates)

Usage:
  CEREBRAS_API_KEY=... uv run python scripts/domain_pipeline.py --domain recepcion --rounds 5
  CEREBRAS_API_KEY=... uv run python scripts/domain_pipeline.py --rounds 3 --target 0.6
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = sys.executable


def run(args: list[str]) -> tuple[int, str]:
    r = subprocess.run([PY] + args, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", default=None)
    ap.add_argument("--rounds", type=int, default=5)
    ap.add_argument("--target", type=float, default=0.60,
                    help="fresh-paraphrase recall floor for certification")
    a = ap.parse_args()

    name = a.domain or "mattress-slice"
    print(f"=== domain pipeline: {name} "
          f"(target recall ≥ {a.target:.0%}, FP = 0) ===\n")
    trajectory = []

    for rnd in range(1, a.rounds + 1):
        dump = Path(tempfile.mkstemp(suffix=".json")[1])
        # Pack domains take both ratchets (strict-rule FN densification +
        # FP fencing). The mature hand-built slice takes FP fencing only:
        # blind densification on a 20-intent interleaved corpus shifts
        # calibration in ways only its own arbitration loops handle.
        args = [str(REPO / "scripts" / "benchmark_matrix.py"),
                "--ingest-fp", "--dump", str(dump)]
        if a.domain:
            args += ["--domain", a.domain, "--ingest-fn"]
        _rc, out = run(args)
        try:
            res = json.loads(dump.read_text())
        except Exception:
            print(out[-1500:])
            sys.exit("benchmark round failed")
        trajectory.append(res)
        print(f"round {rnd}: recall {res['recall']:.0%} "
              f"({res['n']} fresh probes) | FP {res['fp']} | "
              f"near-misses refused {res['tn']}")

        certified = res["fp"] == 0 and res["recall"] >= a.target
        if not a.domain:
            # the hand-built slice re-runs its full gate suite after ingestion
            for script, grep in (("build_index.py", "wrote"),
                                 ("eval_slice.py", "Gate"),
                                 ("probe_conversation.py", "gate")):
                rc, out = run([str(REPO / "scripts" / script)])
                line = next((l for l in out.splitlines() if grep in l), "?")
                print(f"    {script}: {line.strip()[:80]}")
                if script == "eval_slice.py" and "FAIL" in out:
                    sys.exit("    eval gate FAILED after ingestion — "
                             "a mislabeled probe got in; arbitrate first")
        if certified:
            print(f"\n✓ CERTIFIED in round {rnd}: recall "
                  f"{res['recall']:.0%} ≥ {a.target:.0%}, FP = 0")
            break
    else:
        print(f"\n✗ WITHHELD after {a.rounds} rounds — stays in shadow-serve")

    print("\ntrajectory:")
    for i, r in enumerate(trajectory, 1):
        bar = "█" * int(40 * r["recall"])
        print(f"  round {i}: {bar:<40} recall {r['recall']:.0%} | FP {r['fp']}")
    sys.exit(0 if trajectory and trajectory[-1]["fp"] == 0
             and trajectory[-1]["recall"] >= a.target else 1)


if __name__ == "__main__":
    main()
