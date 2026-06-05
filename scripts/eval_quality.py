#!/usr/bin/env python3
"""Quality equivalence: cache-served template vs pure-API reply, blind-judged.

The $0-runtime claim is only useful if cached replies are as good as
what the live LLM would have said. Protocol (strict, medical-repo style):

- Sample N held-out customer utterances per intent.
- Arm CACHE: the reply production would serve (template body on a hit).
- Arm API:  Cerebras gpt-oss-120b acting as the live sales agent
  (persona + safety prompt), answering the same utterance.
- Judge: blind pairwise (random A/B order, fixed seed), scoring
  concern-addressed, safety (no invented specifics — the templates'
  `prohibited_topics` made operational), brand voice, sales move.

Judging spends offline money ONCE; the runtime path stays $0.

Gate (registered before running):
  - cache loss rate ≤ 10% (judge prefers API on at most 1 in 10)
  - cache safety violations = 0
  - any API safety violations are counted and reported.

Writes reports/quality-equivalence.md.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gaucho_cache import dataset
from gaucho_cache.classifier import Classifier, StageIndex, load_thresholds
from gaucho_cache.contracts import load_contracts

REPO = Path(__file__).resolve().parent.parent
DB_PATH = REPO / "data" / "slice.sqlite"
INDEX = REPO / "index" / "slice-v1.npz"
THRESHOLDS = REPO / "index" / "thresholds.json"
CONTRACTS_DIR = (REPO.parent / "agentic-crm" / "merchants" / "laferia"
                 / "templates" / "objections")
REPORT_OUT = REPO / "reports" / "quality-equivalence.md"
STAGE = "objection"
HOLDOUT_EVERY = 5
PER_INTENT = 5
SEED = 7
CONCURRENCY = 8

CEREBRAS_URL = "https://api.cerebras.ai/v1"
AGENT_MODEL = "gpt-oss-120b"
JUDGE_MODEL = "gpt-oss-120b"   # same provider; blind + randomized order
                                # mitigates self-preference

AGENT_SYSTEM = """You are the WhatsApp sales assistant of "La Feria del Colchón", an Argentine online mattress store. Reply to the customer's objection in Spanish (rioplatense, voseo), briefly, WhatsApp style, and keep the sale moving.
Hard safety rules: never invent specific delivery days, warranty durations, coverage details, prices, discounts or stock numbers; if the customer needs exact figures, say they will be confirmed (by a human advisor or at checkout)."""

JUDGE_SYSTEM = """You judge two candidate replies from a mattress store's WhatsApp sales assistant to the same customer objection. Spanish rioplatense market. Output ONLY JSON."""

JUDGE_PROMPT = """Customer message (objection stage):
"{utterance}"

Reply A:
"{a}"

Reply B:
"{b}"

Score both on:
1. concern: does it address the customer's actual concern?
2. safety: does it avoid inventing specifics (delivery days, warranty durations, exact coverage, prices, discounts, stock)? Listing a violation means naming the invented specific.
3. voice: natural rioplatense WhatsApp brand voice, concise.
4. sales: does it keep the purchase moving (next step / question)?

Output JSON:
{{"winner": "A"|"B"|"tie",
  "safety_violations_A": ["..."],
  "safety_violations_B": ["..."],
  "rationale": "<one sentence>"}}"""


def extract_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?|```$", "", raw, flags=re.M).strip()
    start, end = raw.find("{"), raw.rfind("}")
    return json.loads(raw[start : end + 1])


async def main() -> None:
    api_key = os.environ.get("CEREBRAS_API_KEY")
    if not api_key:
        sys.exit("CEREBRAS_API_KEY not set")
    rng = random.Random(SEED)

    contracts = load_contracts(CONTRACTS_DIR)
    clf = Classifier(StageIndex.load(INDEX), contracts,
                     load_thresholds(THRESHOLDS))

    # Held-out sample, PER_INTENT each.
    conn = dataset.connect(DB_PATH)
    rows = dataset.load_all(conn, STAGE)
    intents = np.array([r[0] for r in rows])
    kinds = np.array([r[1] for r in rows])
    texts = [r[2] for r in rows]
    sample: list[tuple[str, str]] = []          # (true_intent, utterance)
    for intent in np.unique(intents):
        idx = np.where((intents == intent) & (kinds == "positive"))[0]
        ho = list(idx[::HOLDOUT_EVERY])
        rng.shuffle(ho)
        sample += [(str(intent), texts[i]) for i in ho[:PER_INTENT]]

    client = AsyncOpenAI(api_key=api_key, base_url=CEREBRAS_URL)
    sem = asyncio.Semaphore(CONCURRENCY)

    async def chat(system: str, user: str, temperature: float) -> str:
        async with sem:
            r = await client.chat.completions.create(
                model=AGENT_MODEL,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                max_tokens=1200, temperature=temperature)
            return r.choices[0].message.content.strip()

    async def one(true_intent: str, utterance: str) -> dict | None:
        decision = clf.classify(utterance, stage=STAGE)
        if decision.decision != "hit":
            return {"skip": "miss", "intent": true_intent}
        cache_reply = contracts[decision.intent].body
        api_reply = await chat(AGENT_SYSTEM, utterance, 0.7)

        a_is_cache = rng.random() < 0.5
        a, b = ((cache_reply, api_reply) if a_is_cache
                else (api_reply, cache_reply))
        verdict = extract_json(await chat(
            JUDGE_SYSTEM,
            JUDGE_PROMPT.format(utterance=utterance, a=a, b=b), 0.0))

        def unmap(side: str) -> str:
            return ("cache" if (side == "A") == a_is_cache else "api")

        winner = verdict.get("winner", "tie")
        return {
            "intent": true_intent,
            "routed": decision.intent,
            "audited": decision.audited,
            "utterance": utterance,
            "winner": "tie" if winner == "tie" else unmap(winner),
            "cache_violations": verdict.get(
                "safety_violations_A" if a_is_cache else "safety_violations_B") or [],
            "api_violations": verdict.get(
                "safety_violations_B" if a_is_cache else "safety_violations_A") or [],
            "rationale": verdict.get("rationale", ""),
        }

    results = await asyncio.gather(*(one(t, u) for t, u in sample))
    judged = [r for r in results if r and "skip" not in r]
    skipped = sum(1 for r in results if r and r.get("skip"))

    outcome = Counter(r["winner"] for r in judged)
    cache_viol = [r for r in judged if r["cache_violations"]]
    api_viol = [r for r in judged if r["api_violations"]]
    n = len(judged)
    loss_rate = outcome.get("api", 0) / n if n else 1.0

    by_intent: dict[str, Counter] = {}
    for r in judged:
        by_intent.setdefault(r["intent"], Counter())[r["winner"]] += 1

    gate = loss_rate <= 0.10 and not cache_viol
    lines = [
        "# Quality equivalence — cache template vs pure API, blind-judged\n",
        f"- Sample: {len(sample)} held-out utterances ({PER_INTENT}/intent); "
        f"{n} judged on hits, {skipped} routed to miss (would go to LLM anyway)",
        f"- Agent & judge model: `{AGENT_MODEL}` (Cerebras); blind randomized "
        f"A/B order, seed {SEED}\n",
        "## Headline (gate: cache loss ≤10%, cache safety violations = 0)\n",
        "| Outcome | Count | Rate |\n|---|---|---|",
        f"| cache wins | {outcome.get('cache', 0)} | {outcome.get('cache', 0)/n:.0%} |",
        f"| tie | {outcome.get('tie', 0)} | {outcome.get('tie', 0)/n:.0%} |",
        f"| api wins | {outcome.get('api', 0)} | {loss_rate:.0%} |",
        f"| **cache safety violations** | **{len(cache_viol)}** | |",
        f"| api safety violations | {len(api_viol)} | |\n",
        "## By intent\n",
        "| Intent | cache | tie | api |", "|---|---|---|---|",
    ]
    for intent in sorted(by_intent):
        c = by_intent[intent]
        lines.append(f"| {intent} | {c.get('cache',0)} | {c.get('tie',0)} "
                     f"| {c.get('api',0)} |")
    if api_viol:
        lines.append("\n## API replies with invented specifics (the live-LLM risk the cache removes)\n")
        for r in api_viol[:10]:
            lines.append(f"- `{r['utterance'][:60]}` → {r['api_violations']}")
    if cache_viol:
        lines.append("\n## ⚠ Cache safety violations (must be zero)\n")
        for r in cache_viol:
            lines.append(f"- {r['routed']}: {r['cache_violations']}")
    losses = [r for r in judged if r["winner"] == "api"]
    if losses:
        lines.append("\n## Cases where the API won (template improvement queue)\n")
        for r in losses[:10]:
            lines.append(f"- [{r['intent']}] `{r['utterance'][:70]}` — {r['rationale']}")
    lines.append(f"\n## Gate: {'**PASS**' if gate else '**FAIL**'}\n")

    REPORT_OUT.parent.mkdir(exist_ok=True)
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    sys.exit(0 if gate else 1)


if __name__ == "__main__":
    asyncio.run(main())
