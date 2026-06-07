#!/usr/bin/env python3
"""The situation matrix: the medical book's benchmark, ported whole.

models-medical-evaluation's central move: take each cached situation,
hammer it with a DENSE MATRIX of paraphrases (dense variants took recall
48.5% → 95%) and with hard negatives (→ 100% precision). This script is
that benchmark for conversation caches — with one upgrade: every probe
is FRESH (generated now, never seen by the corpus or the calibration),
so nothing is graded on its own homework.

Per cached situation (an audited intent + its template):
  TRUE PROBES   length {short, medium, long} × register {casual voseo,
                formal usted, typos/abbreviations} — the WhatsApp axes —
                K per cell. Every one should HIT this intent (recall).
  NEAR-MISSES   messages that SHARE VOCABULARY with the situation but
                mean something else, so serving this template would be
                wrong. Every serve of THIS intent on one of these is a
                FALSE POSITIVE. Gate: FP = 0, the medical bar.

Works on ANY domain pack — the hand-built mattress slice or a
traffic-distilled pack (this is the certification step before a
distilled domain is allowed into serve mode).

Usage:
  uv run python scripts/benchmark_matrix.py                    # mattress slice
  uv run python scripts/benchmark_matrix.py --domain recepcion # distilled pack
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from gaucho_cache import spend
from gaucho_cache.cerebras import BatchClient
from gaucho_cache.classifier import Classifier, StageIndex, load_thresholds
from gaucho_cache.contracts import MatchContract, load_all_contracts

K_PER_CELL = 3
LENGTHS = [("short", "1-4 words, fragment-style"),
           ("medium", "one natural sentence"),
           ("long", "2-3 sentences with harmless extra context")]
REGISTERS = [("casual", "casual rioplatense voseo"),
             ("formal", "formal usted, complete sentences"),
             ("typos", "lowercase, typos, abbreviations (q, xq, tmb)")]
N_NEAR_MISS = 8

GEN_SYS = ("You write realistic WhatsApp messages from Argentine customers. "
           "Output ONLY a JSON array of strings (escape quotes, no trailing "
           "commas).")
TRUE_PROMPT = """An assistant has this approved reply on file:
"{template}"
(intent name: {intent})

Write {k} customer messages for which this reply is the CORRECT and
complete answer. Length: {length}. Register: {register}.
Each message must be answerable by the reply above verbatim."""

MISS_PROMPT = """An assistant has this approved reply on file:
"{template}"
(intent name: {intent})

Write {n} customer messages that a careless cache WOULD confuse with that
intent — they share its vocabulary and surface shape — but where sending
that reply would be WRONG (the customer means something else, asks for a
different specific, or attaches a condition the reply ignores). Mix of
lengths and registers."""


def load_stack(domain: str | None):
    if domain:
        pack = REPO / "data" / "domains" / domain
        variants = json.loads((pack / "variants.json").read_text())
        contracts = {i: MatchContract(template_id=f"{i.upper()}-auto",
                                      category=i, version=1, audited=True,
                                      body=v[0])
                     for i, v in variants.items()}
        clf = Classifier(StageIndex.load(pack / "index.npz"), contracts,
                         load_thresholds(pack / "thresholds.json"))
        stage = domain
    else:
        contracts = load_all_contracts(
            REPO, REPO / "data" / "contract_extensions.yaml")
        clf = Classifier(StageIndex.load(REPO / "index" / "slice-v1.npz"),
                         contracts,
                         load_thresholds(REPO / "index" / "thresholds.json"))
        stage = "objection"
    situations = {c.category: c.body for c in contracts.values()
                  if c.audited and c.body}
    return clf, situations, stage


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", default=None,
                    help="distilled pack name; default = mattress slice")
    ap.add_argument("--ingest-fp", action="store_true",
                    help="write FPs into the distilled pack as hard negatives "
                         "(the medical book's +negatives move, automated)")
    a = ap.parse_args()

    clf, situations, stage = load_stack(a.domain)
    print(f"{len(situations)} cached situations "
          f"({a.domain or 'mattress slice'})\n")
    client = BatchClient("benchmark_matrix")

    async def gen_true(intent, body, lk, ld, rk, rd):
        try:
            v = await client.chat_json(GEN_SYS, TRUE_PROMPT.format(
                template=body, intent=intent, k=K_PER_CELL,
                length=ld, register=rd), temperature=0.9)
            return intent, lk, rk, [str(x) for x in v][:K_PER_CELL]
        except Exception:
            return intent, lk, rk, []

    async def gen_miss(intent, body):
        try:
            v = await client.chat_json(GEN_SYS, MISS_PROMPT.format(
                template=body, intent=intent, n=N_NEAR_MISS), temperature=0.9)
            return intent, [str(x) for x in v][:N_NEAR_MISS]
        except Exception:
            return intent, []

    trues = await asyncio.gather(*(
        gen_true(i, b, lk, ld, rk, rd)
        for i, b in situations.items()
        for lk, ld in LENGTHS for rk, rd in REGISTERS))
    misses = await asyncio.gather(*(gen_miss(i, b)
                                    for i, b in situations.items()))

    # ---- classify (local, free) ---------------------------------------------
    cell_hit = defaultdict(lambda: [0, 0])     # (length, register) -> [hit, n]
    per_intent = defaultdict(lambda: [0, 0])   # intent -> [hit, n]
    fn_reasons = defaultdict(int)
    SOCIAL = {"greet", "thanks_goodbye", "confirmation", "declination",
              "answer_for_whom"}
    FUNNEL = {"want_to_buy", "answer_size_posture", "answer_for_whom",
              "ask_recommendation"}
    for intent, lk, rk, probes in trues:
        for t in probes:
            d = clf.classify(t, stage=stage)
            # doctrine parity: in-cluster serves are correct (a probe for
            # answer_for_whom served by want_to_buy advances the same move)
            ok = d.serve_eligible and (
                d.intent == intent or {d.intent, intent} <= SOCIAL
                or {d.intent, intent} <= FUNNEL)
            cell_hit[(lk, rk)][0] += ok
            cell_hit[(lk, rk)][1] += 1
            per_intent[intent][0] += ok
            per_intent[intent][1] += 1
            if not ok:
                fn_reasons[d.reason or
                           (f"served_{d.intent}" if d.serve_eligible
                            else "miss")] += 1

    fp = []
    tn = 0
    for intent, probes in misses:
        for t in probes:
            d = clf.classify(t, stage=stage)
            if d.serve_eligible and d.intent == intent:
                fp.append((intent, t))
            else:
                tn += 1

    # ---- report (the medical book's tables) ----------------------------------
    tot_hit = sum(h for h, _ in per_intent.values())
    tot_n = sum(n for _, n in per_intent.values())
    print("RECALL MATRIX (fresh paraphrases that must HIT)")
    print(f"{'':10s}" + "".join(f"{rk:>10s}" for rk, _ in REGISTERS))
    for lk, _ in LENGTHS:
        row = "".join(
            f"{cell_hit[(lk, rk)][0]}/{cell_hit[(lk, rk)][1]:<7}"
            .rjust(10) for rk, _ in REGISTERS)
        print(f"{lk:10s}{row}")
    print(f"\nper-situation recall (worst 6):")
    for i, (h, n) in sorted(per_intent.items(), key=lambda kv: kv[1][0] / max(1, kv[1][1]))[:6]:
        print(f"  {i:38s} {h}/{n}")
    print(f"\nfalse-negative reasons: "
          + ", ".join(f"{k}×{v}" for k, v in
                      sorted(fn_reasons.items(), key=lambda kv: -kv[1])))
    print(f"\nHEADLINE: recall {tot_hit}/{tot_n} = {tot_hit/max(1,tot_n):.0%} "
          f"| near-misses refused {tn}/{tn+len(fp)} "
          f"| FALSE POSITIVES: {len(fp)} (gate: 0)")
    for i, t in fp[:8]:
        print(f"  FP [{i}] {t!r}")
    if fp and a.ingest_fp and a.domain:
        import numpy as np
        from gaucho_cache.classifier import Embedder
        pack = REPO / "data" / "domains" / a.domain
        idx = StageIndex.load(pack / "index.npz")
        vecs = Embedder().encode([t for _i, t in fp])
        idx2 = StageIndex(
            np.vstack([idx.embeddings, vecs]),
            np.concatenate([idx.intents, np.array([i for i, _t in fp])]),
            np.concatenate([idx.kinds, np.array(["negative"] * len(fp))]),
            np.concatenate([idx.actual_intents, np.array(["other"] * len(fp))]))
        idx2.save(pack / "index.npz")
        print(f"→ ingested {len(fp)} FPs as pack negatives (re-run to certify)")
    print(f"ledger ${spend.spent():.2f}")
    sys.exit(1 if fp else 0)


if __name__ == "__main__":
    asyncio.run(main())
