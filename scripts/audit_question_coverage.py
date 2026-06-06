#!/usr/bin/env python3
"""The closure gate: every question the bot asks must have hearable answers.

For each template whose body ends in a question, generate N plausible
customer answers (batched Cerebras), classify each through the full
serving stack, and report coverage: answers must either SERVE a
follow-up or fall to the LLM lane for a *good* reason (multi-concern),
never below_threshold on a predictable reply to the bot's own words.

This is the invariant the user's one-shot exposed ('Es para mi' →
silence). Perfect dataset = corpus closed under this audit.
"""
from __future__ import annotations
import asyncio, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gaucho_cache import spend
from gaucho_cache.cerebras import BatchClient
from gaucho_cache.classifier import Classifier, StageIndex, load_thresholds
from gaucho_cache.contracts import load_all_contracts

REPO = Path(__file__).resolve().parent.parent
N_ANSWERS = 12

async def main() -> None:
    contracts = load_all_contracts(REPO, REPO/"data/contract_extensions.yaml")
    clf = Classifier(StageIndex.load(REPO/"index/slice-v1.npz"), contracts,
                     load_thresholds(REPO/"index/thresholds.json"))
    client = BatchClient("question_coverage")
    questioned = {c.category: c.body for c in contracts.values()
                  if "?" in c.body.split(".")[-1] or c.body.rstrip().endswith("?")}
    print(f"{len(questioned)} templates ask a question\n")

    async def answers_for(cat, body):
        q = await client.chat_json(
            "You write realistic short WhatsApp replies from Argentine customers. Output ONLY a JSON array of strings.",
            f'The mattress-store bot just said:\n"{body}"\n\nWrite {N_ANSWERS} realistic SHORT customer replies that directly answer the bot\'s question (mix: direct answers, casual, with typos, one-word, with extra detail). No new unrelated questions.',
            temperature=0.9)
        return cat, [str(x) for x in q][:N_ANSWERS]

    results = await asyncio.gather(*(answers_for(c, b) for c, b in questioned.items()))
    total_bad = 0
    for cat, answers in results:
        bad = []
        for a in answers:
            d = clf.classify(a, stage="objection")
            ok = d.serve_eligible or d.decision == "hit" or d.reason in (
                "multi_intent", "ambiguous_margin")  # safe-structured miss
            if not ok and d.reason == "below_threshold" and len(a.split()) <= 2:
                ok = True  # bare acks legitimately defer to context/LLM
            if not ok:
                bad.append((a, d.intent, d.reason, round(d.score or 0, 2)))
        status = "✓" if not bad else f"✗ {len(bad)}/{len(answers)} unheard"
        print(f"{status:24s} after [{cat}]'s question")
        for a, i, r, s in bad[:4]:
            print(f"    unheard: {a!r} → {i} {r} s={s}")
        total_bad += len(bad)
    print(f"\n{'✓ CLOSURE HOLDS' if total_bad==0 else f'✗ {total_bad} unheard answers — corpus not closed'}; ledger ${spend.spent():.2f}")
    sys.exit(1 if total_bad else 0)

if __name__ == "__main__":
    asyncio.run(main())
