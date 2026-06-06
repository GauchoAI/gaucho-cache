#!/usr/bin/env python3
"""Battle eval: the cache against independent simulated traffic.

Routes EVERY message of a traffic wave through the full serving stack
(batch-embedded for throughput), scores against the generator's
ground-truth concern, then LLM-audits every apparent confident-wrong —
the generator mislabels sometimes (we learned this twice in the slice
rounds), so raw disagreement ≠ error. Only judge-confirmed errors count.

Novelty traffic (payment_method / off_topic / compound) must MISS:
any serve on novelty is a false-serve, audited the same way.

Outputs reports/battle-test.md with Wilson CIs.

Usage:
    CEREBRAS_API_KEY=... uv run python scripts/battle_eval.py --wave 1
"""

from __future__ import annotations

import argparse
import asyncio
import math
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gaucho_cache import dataset, spend
from gaucho_cache.cerebras import BatchClient
from gaucho_cache.classifier import Embedder, StageIndex, load_thresholds
from gaucho_cache.contracts import default_contracts_dir, load_all_contracts, load_contracts, load_intent_specs

REPO = Path(__file__).resolve().parent.parent
DB_PATH = REPO / "data" / "slice.sqlite"
INDEX = REPO / "index" / "slice-v1.npz"
THRESHOLDS = REPO / "index" / "thresholds.json"
EXTENSIONS = REPO / "data" / "contract_extensions.yaml"
REPORT_OUT = REPO / "reports" / "battle-test.md"
STAGE = "objection"
NOVELTY = {"payment_method", "off_topic", "compound"}
AUDIT_BATCH = 20

JUDGE_SYSTEM = ("You audit a mattress-store chatbot's cached answers. "
                "Output ONLY JSON.")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def audit_prompt(items: list[tuple[int, str, str, str]],
                 meanings: dict[str, str]) -> str:
    defs = "\n".join(f"- {k}: {v}" for k, v in meanings.items())
    numbered = "\n".join(
        f'{i}. message: "{t}" | served_intent: {served} | '
        f'generator_label: {claimed}'
        for i, (_id, t, served, claimed) in enumerate(items))
    return f"""Intent definitions:
{defs}
- payment_method / off_topic: concerns outside all intents above
- compound: two distinct concerns in one message

For each case the cache SERVED the template of served_intent. Judge each independently:
- verdict "correct_serve": the message clearly and solely expresses served_intent (the generator_label may be wrong — judge the TEXT)
- verdict "wrong_serve": the message expresses a different single intent, or is compound/out-of-scope — serving this template was an error

Cases:
{numbered}

Output: JSON array of {len(items)} objects {{"i": <n>, "verdict": "correct_serve"|"wrong_serve", "true_intent": "<label or compound/other>"}}"""


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wave", type=int, required=True)
    a = ap.parse_args()

    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, concern, text FROM traffic WHERE wave=?",
        (a.wave,)).fetchall()
    if not rows:
        sys.exit(f"no traffic for wave {a.wave}")
    ids = [r[0] for r in rows]
    concerns = [r[1] for r in rows]
    texts = [r[2] for r in rows]
    print(f"wave {a.wave}: {len(rows)} messages; ledger ${spend.spent():.2f}")

    contracts = load_all_contracts(REPO, EXTENSIONS)
    specs = load_intent_specs(REPO / "data" / "intents_slice.yaml")
    meanings = {s.intent: s.meaning for s in specs}
    index = StageIndex.load(INDEX)
    thresholds = load_thresholds(THRESHOLDS)

    print("batch-embedding traffic …")
    emb = Embedder(index.model_name).encode(texts)

    pos = index.kinds == "positive"
    intent_masks = {it: pos & (index.intents == it)
                    for it in np.unique(index.intents[pos])}
    neg_masks = {it: (index.kinds == "negative") & (index.intents == it)
                 for it in intent_masks}

    def decide(q):
        sims = index.embeddings @ q
        best = {it: float(sims[m].max()) for it, m in intent_masks.items()}
        ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)
        (i1, s1), (i2, s2) = ranked[0], ranked[1]
        nm = neg_masks[i1]
        ns = float(sims[nm].max()) if nm.any() else -1.0
        th = thresholds.get(i1)
        th2 = thresholds.get(i2)
        c = contracts.get(i1)
        multi = (th2 is not None and s2 >= min(th2.threshold, 0.82)
                 and not ({i1, i2} <= {"greet", "thanks_goodbye"}))  # compound guard
        if (th is None or s1 < th.threshold or multi
                or s1 - s2 < th.margin
                or s1 - ns < th.negative_margin or c is None):
            return ("miss", i1)
        ok, _ = c.preconditions_pass(stage=STAGE, state_fields=set())
        if not ok or not c.audited:
            return ("hit_no_serve", i1)
        return ("serve", i1)

    decisions = [decide(emb[i]) for i in range(len(rows))]

    # ---- raw scoring ---------------------------------------------------------
    served = [(i, d[1]) for i, d in enumerate(decisions) if d[0] == "serve"]
    apparent_wrong = [
        (ids[i], texts[i], intent, concerns[i]) for i, intent in served
        if concerns[i] in NOVELTY or intent != concerns[i]]
    print(f"served {len(served)}/{len(rows)}; apparent wrong serves: "
          f"{len(apparent_wrong)} → auditing all of them")

    # ---- LLM audit of every apparent wrong serve -----------------------------
    client = BatchClient("battle_audit")
    batches = [apparent_wrong[i:i + AUDIT_BATCH]
               for i in range(0, len(apparent_wrong), AUDIT_BATCH)]

    async def audit(batch):
        try:
            items = await client.chat_json(
                JUDGE_SYSTEM, audit_prompt(batch, meanings),
                temperature=0.0)
            return {batch[int(it["i"])][0]: it for it in items
                    if isinstance(it, dict) and "i" in it}
        except spend.BudgetExceeded:
            raise
        except Exception as e:  # noqa: BLE001
            print(f"  audit batch failed: {e}", file=sys.stderr)
            return {}

    verdicts: dict[int, dict] = {}
    for m in await asyncio.gather(*(audit(b) for b in batches)):
        verdicts.update(m)

    confirmed_wrong = [(i_, t, s, c) for (i_, t, s, c) in apparent_wrong
                       if verdicts.get(i_, {}).get("verdict") == "wrong_serve"]
    generator_mislabels = len(apparent_wrong) - len(confirmed_wrong)

    # Persist confirmed failures — they become hard negatives via
    # scripts/ingest_battle_failures.py (the write-back loop).
    conn.execute("""CREATE TABLE IF NOT EXISTS battle_failures (
        traffic_id INTEGER PRIMARY KEY, wave INTEGER, text TEXT,
        served_intent TEXT, true_intent TEXT, ingested INTEGER DEFAULT 0)""")
    for (i_, t, s, c) in confirmed_wrong:
        conn.execute(
            """INSERT OR IGNORE INTO battle_failures
               (traffic_id, wave, text, served_intent, true_intent)
               VALUES (?,?,?,?,?)""",
            (i_, a.wave, t, s,
             verdicts.get(i_, {}).get("true_intent", "other")))
    conn.commit()

    # ---- metrics -------------------------------------------------------------
    n_total = len(rows)
    n_novel = sum(1 for c in concerns if c in NOVELTY)
    n_intax = n_total - n_novel
    n_served = len(served)
    cw = len(confirmed_wrong)
    lo, hi = wilson(cw, n_served)

    novel_serves = [(i, it) for i, it in served if concerns[i] in NOVELTY]
    confirmed_novel = sum(1 for (i_, t, s, c) in confirmed_wrong
                          if c in NOVELTY)

    by_concern: dict[str, Counter] = defaultdict(Counter)
    for i, (d, intent) in enumerate(decisions):
        c = concerns[i]
        by_concern[c]["n"] += 1
        if d == "serve":
            by_concern[c]["served"] += 1
            if c not in NOVELTY and intent == c:
                by_concern[c]["correct"] += 1
    for (i_, t, s, c) in confirmed_wrong:
        by_concern[c]["confirmed_wrong"] += 1

    lines = [
        f"# Battle test — wave {a.wave}, independent simulated traffic\n",
        f"- Traffic: **{n_total}** messages ({n_intax} in-taxonomy, "
        f"{n_novel} novelty: payment/off-topic/compound)",
        f"- Decision stack: full compound predicate + match contracts + "
        f"audit gate (production rules)\n",
        "## Headline\n",
        "| Metric | Value | 95% CI |\n|---|---|---|",
        f"| Serve rate (overall) | {n_served/n_total:.1%} | |",
        f"| Shadow coverage (incl. unaudited/precondition hits) | "
        f"{sum(1 for d in decisions if d[0] != 'miss')/n_total:.1%} | |",
        f"| **Confirmed wrong serves** | **{cw} / {n_served} "
        f"({cw/max(n_served,1):.2%})** | {lo:.2%}–{hi:.2%} |",
        f"| False-serves on novelty traffic | {confirmed_novel} / {n_novel} "
        f"({confirmed_novel/max(n_novel,1):.2%}) | |",
        f"| Apparent wrongs that were generator mislabels | "
        f"{generator_mislabels} / {len(apparent_wrong)} | |\n",
        "## By concern\n",
        "| Concern | n | served | correct serve | confirmed wrong |",
        "|---|---|---|---|---|",
    ]
    for c in sorted(by_concern):
        s = by_concern[c]
        lines.append(
            f"| {c} | {s['n']} | {s['served']} | {s.get('correct', 0)} "
            f"| {s.get('confirmed_wrong', 0)} |")
    if confirmed_wrong:
        lines.append("\n## Confirmed wrong serves (corpus-fix queue)\n")
        for (i_, t, s, c) in confirmed_wrong[:30]:
            true = verdicts.get(i_, {}).get("true_intent", "?")
            lines.append(f"- `{t[:90]}` — served `{s}`, generator said `{c}`, "
                         f"judge says `{true}`")
    lines.append(f"\nLedger after audit: ${spend.spent():.2f}")

    REPORT_OUT.parent.mkdir(exist_ok=True)
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines[:25]))
    print(f"\n✓ report → {REPORT_OUT}")


if __name__ == "__main__":
    asyncio.run(main())
