#!/usr/bin/env python3
"""Offline real-phrasing certification for the service pack — drive lies→0.

The held-out set must not be tuned against (overfit risk). So certify on
FRESH probes instead: each round, generate a balanced validation set —
real-seed paraphrases per service intent (must SERVE) + near-miss
non-service phrasings (must FORWARD) — measure false-positives, mine them
into hard negatives, recalibrate, and repeat until FP≈0 on a fresh draw.
The held-out is measured ONCE at the end to confirm the lie-reduction
transfers (not to tune).

This is the medical "+negatives → precision" recipe and chapter 26's
"pre-certify offline because $0 forbids runtime verification", made
concrete for the service domain.

Usage: CEREBRAS_API_KEY=... uv run python scripts/certify_service.py --rounds 4
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from gaucho_cache import service as svc
from gaucho_cache import spend
from gaucho_cache.cerebras import BatchClient
from gaucho_cache.classifier import (Classifier, Embedder, StageIndex,
                                     load_thresholds)
from gaucho_cache.contracts import MatchContract

PACK = REPO / "data" / "domains" / "cocoshoes-service"
LABELS = REPO / "reports" / "coco_labels.json"

# non-service concepts that must FORWARD (the lie sources). Fresh each round.
NEAR_MISS = {
    "purchase": "wanting to BUY a specific shoe (not a return/exchange)",
    "deep_fit": "detailed size/fit advice needing judgment (horma, '38 pero "
                "me queda grande', medidas del pie)",
    "problem_on_order": "an order number PLUS a novel problem needing a human "
                        "(defective, wrong item, confusing email)",
    "website_bug": "a website/checkout problem ('el talle no deja "
                   "seleccionar', 'no toma el cupón')",
    "logistics_statement": "statements during a chat that ask nothing "
                           "actionable ('recién estuvimos en el local')",
    "chitchat": "conversational glue / apologies / vague acks ('perdón la "
                "molestia', 'pruebo más tarde')",
}


def serve(clf, msg):
    """Mirror reality_coverage's service serving path → (intent, reason)|None."""
    fi = svc.detect_fact_intent(msg)
    if fi and svc.extract_order_id(msg) is None:
        r = svc.serve_service(fi, msg)
        if r:
            return fi, r[1]
    cd = clf.classify(msg[:200], stage="svc")
    if cd.intent in ("greeting", "thanks_closing"):
        rest = __import__("gaucho_cache.classifier", fromlist=["strip_salutation"]).strip_salutation(msg)
        if rest:
            cd2 = clf.classify(rest[:200], stage="svc")
            if cd2.serve_eligible and cd2.intent in svc.SERVICE_CLUSTER:
                cd = cd2
    if cd.serve_eligible:
        r = svc.serve_service(cd.intent, msg)
        if r:
            return cd.intent, r[1]
        if cd.intent in ("greeting", "thanks_closing"):
            return cd.intent, "template"
    return None


def load_clf():
    variants = json.loads((PACK / "variants.json").read_text())
    contracts = {i: MatchContract(template_id=i, category=i, version=1,
                                  audited=True, body=v[0])
                 for i, v in variants.items()}
    return Classifier(StageIndex.load(PACK / "index.npz"), contracts,
                      load_thresholds(PACK / "thresholds.json"))


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--per", type=int, default=20)
    a = ap.parse_args()
    client = BatchClient("certify_service")
    emb = Embedder()
    # real seeds per service intent (train side) for true-probe generation
    rows = json.loads(LABELS.read_text())
    TOPIC = {"order_status": "order_status", "exchange_return": "exchange_return",
             "shipping_coordination": "shipping_coordination",
             "complaint_problem": "complaint_problem"}
    seeds = {}
    for r in rows:
        if r["conv"] % 10 >= 3 and TOPIC.get(r["topic"]):
            seeds.setdefault(TOPIC[r["topic"]], []).append(r["msg"][:160])

    async def gen(desc, n):
        out = []
        while len(out) < n:
            try:
                v = await client.chat_json(
                    "You write realistic Argentine shoe-store WhatsApp "
                    "messages. Output ONLY a JSON array of strings.",
                    f"Write 20 messages: {desc}. Rioplatense, varied length.",
                    temperature=0.95, max_tokens=2000)
                out += [str(x) for x in v][:20]
            except Exception:
                break
        return out[:n]

    for rnd in range(1, a.rounds + 1):
        clf = load_clf()
        # fresh validation set
        true_sets = await asyncio.gather(*(
            gen(f"with intent '{i}', like: {seeds[i][:6]}", a.per)
            for i in seeds))
        near = await asyncio.gather(*(gen(d, a.per) for d in NEAR_MISS.values()))

        recall_hit = recall_n = 0
        fps = []
        for i, probes in zip(seeds, true_sets):
            for m in probes:
                recall_n += 1
                s = serve(clf, m)
                if s and (s[0] == i or s[0] in svc.SERVICE_CLUSTER):
                    recall_hit += 1
        for probes in near:
            for m in probes:
                s = serve(clf, m)
                if s is not None:
                    fps.append((s[0], m))
        nmiss = sum(len(p) for p in near)
        print(f"round {rnd}: recall {recall_hit}/{recall_n} "
              f"({recall_hit/max(1,recall_n):.0%}) | FP {len(fps)}/{nmiss} "
              f"({len(fps)/max(1,nmiss):.0%})")
        if not fps:
            print("  ✓ FP=0 on fresh validation — certified")
            break
        # ingest FPs as negatives attached to the intent they wrongly hit
        idx = StageIndex.load(PACK / "index.npz")
        E, I, K, A = (list(idx.embeddings), list(idx.intents),
                      list(idx.kinds), list(idx.actual_intents))
        nv = emb.encode([m for _i, m in fps])
        for j, (owner, _m) in enumerate(fps):
            E.append(nv[j]); I.append(owner)
            K.append("negative"); A.append("other")
        StageIndex(np.array(E), np.array(I), np.array(K),
                   np.array(A)).save(PACK / "index.npz")
        print(f"  + ingested {len(fps)} fresh-validation FPs as negatives")

    print(f"\nledger ${spend.spent():.2f}")


if __name__ == "__main__":
    asyncio.run(main())
