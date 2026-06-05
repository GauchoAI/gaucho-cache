#!/usr/bin/env python3
"""Prove $0 runtime spend: run the full cache path with networking BLOCKED.

The claim "zero USD at runtime" is proven by construction, not by
accounting: every socket connection is denied for the entire process
lifetime (model load included — HF_HUB_OFFLINE forces the local cache).
If any component tried to reach an API, the run would crash. It doesn't.

Measures end-to-end latency (embed → route → compound predicate →
template render) per turn on the held-out eval set.

Writes reports/zero-spend-proof.md.
"""

from __future__ import annotations

import os
import socket
import statistics
import sys
import time
from pathlib import Path

# ---- 1. forbid networking BEFORE any ML import ------------------------------
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
for var in list(os.environ):
    if "API_KEY" in var or "TOKEN" in var:
        del os.environ[var]

_BLOCKED: list[tuple] = []


class _NoNetSocket(socket.socket):
    def connect(self, addr):  # noqa: D102
        _BLOCKED.append(addr)
        raise OSError(f"network blocked by zero-spend proof: {addr}")

    def connect_ex(self, addr):  # noqa: D102
        _BLOCKED.append(addr)
        raise OSError(f"network blocked by zero-spend proof: {addr}")


socket.socket = _NoNetSocket  # type: ignore[misc]

# ---- 2. now load the runtime ------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import numpy as np  # noqa: E402

from gaucho_cache import dataset  # noqa: E402
from gaucho_cache.classifier import Classifier, StageIndex, load_thresholds  # noqa: E402
from gaucho_cache.contracts import load_contracts  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
DB_PATH = REPO / "data" / "slice.sqlite"
INDEX = REPO / "index" / "slice-v1.npz"
THRESHOLDS = REPO / "index" / "thresholds.json"
CONTRACTS_DIR = (REPO.parent / "agentic-crm" / "merchants" / "laferia"
                 / "templates" / "objections")
REPORT_OUT = REPO / "reports" / "zero-spend-proof.md"
STAGE = "objection"
HOLDOUT_EVERY = 5


def main() -> None:
    contracts = load_contracts(CONTRACTS_DIR)
    clf = Classifier(StageIndex.load(INDEX), contracts,
                     load_thresholds(THRESHOLDS))

    # Same held-out set as eval_slice.py.
    conn = dataset.connect(DB_PATH)
    rows = dataset.load_all(conn, STAGE)
    intents = np.array([r[0] for r in rows])
    kinds = np.array([r[1] for r in rows])
    texts = [r[2] for r in rows]
    holdout: list[int] = []
    for intent in np.unique(intents):
        idx = np.where((intents == intent) & (kinds == "positive"))[0]
        holdout.extend(idx[::HOLDOUT_EVERY])

    # Warm-up (model load + first encode happen here, offline).
    t0 = time.perf_counter()
    clf.classify("hola", stage=STAGE)
    warmup_s = time.perf_counter() - t0

    latencies = []
    served = 0
    for i in holdout:
        t0 = time.perf_counter()
        d = clf.classify(texts[i], stage=STAGE)
        if d.serve_eligible:
            _reply = contracts[d.intent].body  # template render (verbatim:
            served += 1                        # slice templates have no slots)
        latencies.append((time.perf_counter() - t0) * 1000)

    p50 = statistics.median(latencies)
    p95 = statistics.quantiles(latencies, n=20)[18]

    lines = [
        "# Zero-spend proof\n",
        "Method: `socket.socket.connect` is replaced with a raising stub for "
        "the entire process (before any import); all `*API_KEY*`/`*TOKEN*` "
        "env vars are deleted; `HF_HUB_OFFLINE=1`. Any attempt by any "
        "component to reach a network endpoint would crash the run.\n",
        "| Metric | Value |\n|---|---|",
        f"| Turns processed | {len(holdout)} |",
        f"| Network connections attempted | **{len(_BLOCKED)}** |",
        f"| API spend | **$0.00 (by construction)** |",
        f"| Serve-eligible (audited hits) | {served} ({served/len(holdout):.0%}) |",
        f"| Latency p50 / p95 | {p50:.1f} ms / {p95:.1f} ms |",
        f"| Cold start (model load + first encode) | {warmup_s:.1f} s |",
    ]
    if _BLOCKED:
        lines.append("\n⚠ blocked attempts: " + ", ".join(map(str, _BLOCKED[:10])))
        lines.append("\n**FAIL — something tried to reach the network.**")
    else:
        lines.append("\n**PASS — the runtime path cannot spend money.**")

    REPORT_OUT.parent.mkdir(exist_ok=True)
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    sys.exit(1 if _BLOCKED else 0)


if __name__ == "__main__":
    main()
