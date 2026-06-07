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

# The medical book's density: 10 length steps x 10 paraphrases = 100
# fresh probes per situation. Register varies WITHIN each batch of 10
# (casual voseo / formal usted / typos+abbreviations) so every length
# step samples every register.
K_PER_LENGTH = 10
LENGTHS = [
    ("L01", "1-2 words, bare fragment"),
    ("L02", "2-3 words"),
    ("L03", "3-5 words, still fragmentary"),
    ("L04", "a short clause, 5-7 words"),
    ("L05", "one short natural sentence"),
    ("L06", "one full sentence, ~10-14 words"),
    ("L07", "one long sentence with a small aside"),
    ("L08", "two sentences"),
    ("L09", "two-three sentences with harmless extra context"),
    ("L10", "three-four sentences, chatty, with harmless digressions"),
]
N_NEAR_MISS = 10

GEN_SYS = ("You write realistic WhatsApp messages from Argentine customers. "
           "Output ONLY a JSON array of strings (escape quotes, no trailing "
           "commas).")
TRUE_PROMPT = """An assistant has this approved reply on file:
"{template}"
(intent name: {intent})

Write {k} DISTINCT customer messages for which this reply is the CORRECT
and complete answer. Length of every message: {length}.
Vary the register across the {k}: some casual rioplatense voseo, some
formal usted, some lowercase with typos and abbreviations (q, xq, tmb).
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
    ap.add_argument("--ingest-fn", action="store_true",
                    help="write missed true-probes into the pack as positives "
                         "(labeled by construction — densification for free)")
    ap.add_argument("--dump", type=Path, default=None,
                    help="write round results as JSON (for the pipeline)")
    a = ap.parse_args()

    clf, situations, stage = load_stack(a.domain)
    print(f"{len(situations)} cached situations "
          f"({a.domain or 'mattress slice'})\n")
    client = BatchClient("benchmark_matrix")

    async def gen_true(intent, body, lk, ld):
        try:
            v = await client.chat_json(GEN_SYS, TRUE_PROMPT.format(
                template=body, intent=intent, k=K_PER_LENGTH,
                length=ld), temperature=0.9)
            return intent, lk, [str(x) for x in v][:K_PER_LENGTH]
        except Exception:
            return intent, lk, []

    async def gen_miss(intent, body):
        try:
            v = await client.chat_json(GEN_SYS, MISS_PROMPT.format(
                template=body, intent=intent, n=N_NEAR_MISS), temperature=0.9)
            return intent, [str(x) for x in v][:N_NEAR_MISS]
        except Exception:
            return intent, []

    trues = await asyncio.gather(*(
        gen_true(i, b, lk, ld)
        for i, b in situations.items() for lk, ld in LENGTHS))
    misses = await asyncio.gather(*(gen_miss(i, b)
                                    for i, b in situations.items()))

    # ---- classify (local, free) ---------------------------------------------
    cell_hit = defaultdict(lambda: [0, 0])     # length -> [hit, n]
    per_intent = defaultdict(lambda: [0, 0])   # intent -> [hit, n]
    fn_reasons = defaultdict(int)
    fn_probes: list[tuple[str, str]] = []
    SOCIAL = {"greet", "thanks_goodbye", "confirmation", "declination",
              "answer_for_whom"}
    FUNNEL = {"want_to_buy", "answer_size_posture", "answer_for_whom",
              "ask_recommendation"}
    for intent, lk, probes in trues:
        for t in probes:
            d = clf.classify(t, stage=stage)
            # doctrine parity: in-cluster serves are correct (a probe for
            # answer_for_whom served by want_to_buy advances the same move)
            ok = d.serve_eligible and (
                d.intent == intent or {d.intent, intent} <= SOCIAL
                or {d.intent, intent} <= FUNNEL)
            cell_hit[lk][0] += ok
            cell_hit[lk][1] += 1
            per_intent[intent][0] += ok
            per_intent[intent][1] += 1
            if not ok:
                fn_probes.append((intent, t))
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
    print("RECALL BY LENGTH (10 fresh paraphrases x situations per row)")
    for lk, ld in LENGTHS:
        h, n = cell_hit[lk]
        bar = "█" * int(40 * h / max(1, n))
        print(f"  {lk} {ld[:34]:36s} {bar:<40} {h}/{n} ({h/max(1,n):.0%})")
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
    if a.domain and (a.ingest_fp or a.ingest_fn):
        import numpy as np
        from gaucho_cache.classifier import Embedder
        pack = REPO / "data" / "domains" / a.domain
        idx = StageIndex.load(pack / "index.npz")
        emb = Embedder()
        E, I, K, A = (idx.embeddings, list(idx.intents), list(idx.kinds),
                      list(idx.actual_intents))
        adds = []
        if a.ingest_fp and fp:
            adds += [(i, t, "negative") for i, t in fp]
        if a.ingest_fn and fn_probes:
            for i, t in fn_probes:
                routed, *_ = clf.route(t)
                if routed != i:
                    continue  # strict: pure density only
                adds.append((i, t, "positive"))
        if adds:
            vecs = emb.encode([t for _i, t, _k in adds])
            E = np.vstack([E, vecs])
            I += [i for i, _t, _k in adds]
            K += [k for _i, _t, k in adds]
            A += ["other" if k == "negative" else "" for _i, _t, k in adds]
            StageIndex(E, np.array(I), np.array(K), np.array(A)).save(
                pack / "index.npz")
            # recalibrate: an intent's threshold sits above what OTHER
            # intents' positives reach into it (distill parity)
            V, In, Kn = E, np.array(I), np.array(K)
            pos = Kn == "positive"
            th = {}
            for intent in sorted(set(In[pos])):
                m = pos & (In == intent)
                o = pos & (In != intent)
                cross = float((V[o] @ V[m].T).max()) if o.any() else 0.6
                th[intent] = {"threshold": min(0.88, cross + 0.02),
                              "margin": 0.05, "negative_margin": 0.03}
            (pack / "thresholds.json").write_text(json.dumps(th, indent=1))
            print(f"→ ingested {sum(1 for *_x, k in adds if k=='negative')} FPs"
                  f" as negatives + {sum(1 for *_x, k in adds if k=='positive')}"
                  f" FNs as positives; thresholds recalibrated")
    if not a.domain and (a.ingest_fp or a.ingest_fn):
        import sqlite3 as _sq
        con = _sq.connect(REPO / "data" / "slice.sqlite")
        cur = con.cursor()
        base = cur.execute("SELECT COALESCE(MAX(variant_index),0)+1 FROM "
                           "variants WHERE register='matrix'").fetchone()[0]
        n_in = 0
        if a.ingest_fn:
            for intent, t in fn_probes:
                # STRICT densification rule: only ingest probes the router
                # already routes to the label (or in-cluster) — "right
                # intent, weak score" is pure density; anything else is
                # generator drift and needs arbitration, not ingestion.
                routed, *_ = clf.route(t)
                if not (routed == intent or {routed, intent} <= SOCIAL
                        or {routed, intent} <= FUNNEL):
                    continue
                try:
                    cur.execute(
                        "INSERT INTO variants (stage,intent,kind,register,"
                        "variant_index,text) VALUES ('objection',?,"
                        "'positive','matrix',?,?)", (intent, base, t))
                    base += 1; n_in += 1
                except _sq.IntegrityError:
                    pass
        if a.ingest_fp:
            for intent, t in fp:
                try:
                    cur.execute(
                        "INSERT INTO variants (stage,intent,kind,register,"
                        "variant_index,text,actual_intent) VALUES "
                        "('objection',?,'negative','matrix',?,?,'other')",
                        (intent, base, t))
                    base += 1; n_in += 1
                except _sq.IntegrityError:
                    pass
        con.commit()
        print(f"→ ingested {n_in} rows into slice.sqlite "
              f"(rebuild_index + eval_slice required)")
    if a.dump:
        a.dump.write_text(json.dumps({
            "recall": tot_hit / max(1, tot_n), "n": tot_n,
            "fp": len(fp), "tn": tn,
            "per_intent": {i: [h, n] for i, (h, n) in per_intent.items()}}))
    print(f"ledger ${spend.spent():.2f}")
    sys.exit(1 if fp else 0)


if __name__ == "__main__":
    asyncio.run(main())
