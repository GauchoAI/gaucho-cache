#!/usr/bin/env python3
"""Mini-E2: embedding-only evaluation of the P0.5 slice (PLAN.md §11).

Protocol:
- Per intent, hold out 20% of positives (every 5th, spanning matrix cells).
- Index = train positives + all hard negatives.
- Calibrate per-intent thresholds on the train side: an intent's
  threshold must sit above what its own hard negatives score against it.
- Evaluate held-out positives through the FULL compound predicate, and
  hard negatives as adversarial queries.

Gate (§11): routing accuracy ≥95% AND confident_wrong_rate = 0.
Miss rate is unconstrained — "a slice that misses often but never lies
passes; a slice that hits 99% with one confident wrong answer fails."

Writes index/thresholds.json and reports/slice-eval.md.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gaucho_cache import dataset
from gaucho_cache.classifier import (DEFAULT_MODEL, Classifier, Embedder,
                                     StageIndex, Thresholds)
from gaucho_cache.contracts import default_contracts_dir, load_contracts

REPO = Path(__file__).resolve().parent.parent
DB_PATH = REPO / "data" / "slice.sqlite"
CONTRACTS_DIR = default_contracts_dir(REPO)
THRESHOLDS_OUT = REPO / "index" / "thresholds.json"
REPORT_OUT = REPO / "reports" / "slice-eval.md"
STAGE = "objection"
HOLDOUT_EVERY = 5           # 20%
MARGIN = 0.05
NEGATIVE_MARGIN = 0.03
THRESHOLD_DELTA = 0.02      # calibrated threshold sits this far above
                            # the worst own-negative score
THRESHOLD_FLOOR = 0.55

CONFUSABLE_PAIRS = [("shipping_time", "shipping_zone"),
                    ("warranty", "return_policy"),
                    ("size_fit", "firmness_doubt"),
                    ("brand_trust", "bot_skepticism")]


def main() -> None:
    conn = dataset.connect(DB_PATH)
    rows = dataset.load_all(conn, STAGE)
    if not rows:
        sys.exit("dataset empty — run scripts/generate_variants.py first")

    intents = np.array([r[0] for r in rows])
    kinds = np.array([r[1] for r in rows])
    texts = [r[2] for r in rows]
    actuals = np.array([r[3] for r in rows])

    print(f"Embedding {len(texts)} variants ({DEFAULT_MODEL}) …")
    emb = Embedder().encode(texts)

    # ---- split: per intent, every Nth positive is held out -----------------
    holdout = np.zeros(len(rows), dtype=bool)
    for intent in np.unique(intents):
        idx = np.where((intents == intent) & (kinds == "positive"))[0]
        holdout[idx[::HOLDOUT_EVERY]] = True
    train = ~holdout

    index = StageIndex(emb[train], intents[train], kinds[train], actuals[train])
    contracts = load_contracts(CONTRACTS_DIR)

    # ---- calibrate per-intent thresholds on train ---------------------------
    # An intent's threshold sits above the best score its OWN hard
    # negatives achieve against its train positives.
    #
    # Battle-ingested negatives are EXCLUDED from this quantile: they are
    # near-positives by construction (they fooled the predicate once) and
    # inflating the global threshold with them collapses serve rate
    # (wave-2 finding: 12.4%→3.5%). They still sit in the index, where
    # the negative-margin leg blocks their precise neighbourhoods.
    battle_texts = set()
    try:
        battle_texts = {r[0] for r in conn.execute(
            "SELECT text FROM battle_failures")}
    except Exception:  # noqa: BLE001 — table may not exist yet
        pass
    is_battle = np.array([t in battle_texts for t in texts])

    thresholds: dict[str, Thresholds] = {}
    for intent in np.unique(intents):
        pos_m = train & (intents == intent) & (kinds == "positive")
        neg_m = (intents == intent) & (kinds == "negative") & ~is_battle
        worst = 0.0
        if pos_m.any() and neg_m.any():
            sims = emb[neg_m] @ emb[pos_m].T          # (n_neg, n_pos)
            # Strict: the threshold sits above what (almost) every own
            # negative achieves. q=0.95 instead of max so one residual
            # mislabeled negative can't disable an intent outright.
            worst = float(np.quantile(sims.max(axis=1), 0.95))
        thresholds[intent] = Thresholds(
            threshold=max(THRESHOLD_FLOOR, worst + THRESHOLD_DELTA),
            margin=MARGIN, negative_margin=NEGATIVE_MARGIN)

    # Classifier.route() re-encodes per call; for eval speed we reuse the
    # batch embeddings and inline the same math.
    def route_from_vec(q):
        sims = index.embeddings @ q
        pos = index.kinds == "positive"
        best = {}
        for it in np.unique(index.intents[pos]):
            m = pos & (index.intents == it)
            best[it] = float(sims[m].max())
        ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)
        (i1, s1), (i2, s2) = ranked[0], ranked[1]
        neg = (index.kinds == "negative") & (index.intents == i1)
        ns = float(sims[neg].max()) if neg.any() else -1.0
        return i1, s1, s1 - s2, s1 - ns, (i2, s2)

    def predicate(intent, score, margin, neg_margin, second=None):
        th = thresholds[intent]
        if score < th.threshold:
            return "below_threshold"
        if second is not None:
            i2, s2 = second
            if i2 in thresholds and s2 >= min(thresholds[i2].threshold, 0.82):
                return "multi_intent"  # compound guard (wave-1 finding)
        if margin < th.margin:
            return "ambiguous_margin"
        if neg_margin < th.negative_margin:
            return "negative_margin"
        return ""  # hit

    # ---- evaluate held-out positives ----------------------------------------
    ho_idx = np.where(holdout)[0]
    n = len(ho_idx)
    top1_correct = 0
    hits = 0
    confident_wrong = []
    confusions = Counter()
    per_intent = defaultdict(lambda: {"n": 0, "top1": 0, "hits": 0, "wrong": 0})

    for i in ho_idx:
        true = intents[i]
        pred, score, margin, neg_margin, second = route_from_vec(emb[i])
        stat = per_intent[true]
        stat["n"] += 1
        if pred == true:
            top1_correct += 1
            stat["top1"] += 1
        else:
            confusions[(true, pred)] += 1
        if not predicate(pred, score, margin, neg_margin, second):
            hits += 1
            stat["hits"] += 1
            if pred != true:
                confident_wrong.append((texts[i], true, pred, score))
                stat["wrong"] += 1

    # ---- adversarial: hard negatives as queries ------------------------------
    neg_idx = np.where(kinds == "negative")[0]
    neg_hits_wrong = []
    for i in neg_idx:
        owner = intents[i]            # the intent this is NOT
        actual = actuals[i] or "other"
        pred, score, margin, neg_margin, second = route_from_vec(emb[i])
        if not predicate(pred, score, margin, neg_margin, second):
            ok = (pred == actual)     # routed to where it truly belongs
            if not ok and (pred == owner or actual == "other"):
                neg_hits_wrong.append((texts[i], owner, actual, pred, score))

    # ---- report --------------------------------------------------------------
    acc = top1_correct / n
    hit_rate = hits / n
    cw_rate = len(confident_wrong) / n

    lines = [
        "# P0.5 slice evaluation — embedding-only (mini-E2)\n",
        f"- Model: `{DEFAULT_MODEL}`",
        f"- Index: {int((kinds[train]=='positive').sum())} train positives "
        f"+ {int((kinds=='negative').sum())} hard negatives; "
        f"{n} held-out positives evaluated\n",
        "## Headline (gate: accuracy ≥95%, confident_wrong = 0)\n",
        f"| Metric | Value |\n|---|---|",
        f"| Routing accuracy (top-1) | **{acc:.1%}** |",
        f"| Hit rate (compound predicate) | {hit_rate:.1%} |",
        f"| Confident-wrong rate | **{cw_rate:.2%}** ({len(confident_wrong)}) |",
        f"| Adversarial negatives confidently mis-served | {len(neg_hits_wrong)} / {len(neg_idx)} |\n",
        "## Per intent\n",
        "| Intent | audited | n | top-1 | hits | confident-wrong |",
        "|---|---|---|---|---|---|",
    ]
    for intent in sorted(per_intent):
        s = per_intent[intent]
        aud = "✓" if contracts.get(intent) and contracts[intent].audited else "✗"
        lines.append(f"| {intent} | {aud} | {s['n']} | {s['top1']/s['n']:.0%} "
                     f"| {s['hits']/s['n']:.0%} | {s['wrong']} |")

    lines += ["\n## Confusable pairs (routing confusions, held-out)\n",
              "| Pair | a→b | b→a |", "|---|---|---|"]
    for a, b in CONFUSABLE_PAIRS:
        lines.append(f"| {a} ↔ {b} | {confusions.get((a, b), 0)} "
                     f"| {confusions.get((b, a), 0)} |")
    other_conf = {k: v for k, v in confusions.items()
                  if (k[0], k[1]) not in [(a, b) for a, b in CONFUSABLE_PAIRS]
                  and (k[1], k[0]) not in [(a, b) for a, b in CONFUSABLE_PAIRS]}
    if other_conf:
        lines.append("\nOther confusions: " + ", ".join(
            f"{a}→{b}×{v}" for (a, b), v in sorted(other_conf.items())))

    if confident_wrong:
        lines.append("\n## Confident-wrong cases (MUST be zero to pass)\n")
        for text, true, pred, score in confident_wrong[:20]:
            lines.append(f"- `{text}` — true `{true}`, served `{pred}` ({score:.3f})")
    if neg_hits_wrong:
        lines.append("\n## Adversarial negatives confidently mis-served\n")
        for text, owner, actual, pred, score in neg_hits_wrong[:20]:
            lines.append(f"- `{text}` — not-{owner} (actually {actual}), "
                         f"served `{pred}` ({score:.3f})")

    gate = acc >= 0.95 and len(confident_wrong) == 0
    lines.append(f"\n## Gate: {'**PASS**' if gate else '**FAIL**'}\n")

    REPORT_OUT.parent.mkdir(exist_ok=True)
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")
    THRESHOLDS_OUT.parent.mkdir(exist_ok=True)
    THRESHOLDS_OUT.write_text(json.dumps(
        {k: vars(v) for k, v in thresholds.items()}, indent=2))

    print("\n".join(lines))
    print(f"\n✓ report → {REPORT_OUT}\n✓ thresholds → {THRESHOLDS_OUT}")
    sys.exit(0 if gate else 1)


if __name__ == "__main__":
    main()
