#!/usr/bin/env python3
"""Quality equivalence v2: cache template vs pure API, judged on an
absolute rubric against the merchant policy book (non-inferiority).

Round-1 methodology corrections (PLAN.md §14):
- The API arm now gets the merchant policy book in its system prompt —
  production prompts include policies, so the round-1 API arm was
  unrealistically unconstrained AND unfairly judged.
- The judge receives the policy book as verified ground truth: a safety
  violation is a specific factual claim NOT backed by the book. Round 1
  flagged audited merchant facts (CACE membership, cuotas) as
  "invented" for lack of this reference.
- Scoring is ABSOLUTE per reply (concern addressed / safety / voice /
  next step), not winner-take-all pairwise: "same quality" is a
  non-inferiority claim, and pairwise preference converts stylistic
  tailoring deltas into losses. Pairwise verdict is kept as secondary.
- Serving preconditions are enforced (contract_extensions.yaml):
  out_of_stock_reservation requires known stock state → misses here.

Gate:
  cache safety rate = 100%  (vs policy book)
  AND mean cache rubric ≥ mean API rubric − 0.05  (non-inferiority)

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
EXTENSIONS = REPO / "data" / "contract_extensions.yaml"
REPORT_OUT = REPO / "reports" / "quality-equivalence.md"
STAGE = "objection"
HOLDOUT_EVERY = 5
PER_INTENT = 5
SEED = 7
CONCURRENCY = 8
NON_INFERIORITY_MARGIN = 0.05

CEREBRAS_URL = "https://api.cerebras.ai/v1"
MODEL = "gpt-oss-120b"

AGENT_SYSTEM = """You are the WhatsApp sales assistant of "La Feria del Colchón", an Argentine online mattress store. Reply to the customer's objection in Spanish (rioplatense, voseo), briefly, WhatsApp style, and keep the sale moving.
Hard safety rules: never state specifics (delivery days, warranty durations, coverage, prices, discounts, stock) unless they appear in the APPROVED POLICY BOOK below; if the customer needs exact figures beyond it, say they will be confirmed (by a human advisor or at checkout).

APPROVED POLICY BOOK (verified merchant answers per concern — you may paraphrase):
{book}"""

JUDGE_SYSTEM = ("You audit two candidate replies from a mattress store's "
                "WhatsApp sales assistant. Output ONLY JSON.")

JUDGE_PROMPT = """VERIFIED MERCHANT POLICY BOOK (ground truth — claims consistent with it are NOT invented):
{book}

Customer message (objection stage):
"{utterance}"

Reply A:
"{a}"

Reply B:
"{b}"

Score EACH reply independently, binary per criterion:
- concern: addresses the customer's actual concern (1/0)
- safety: every specific factual claim (durations, prices, coverage, memberships, processes) is backed by the policy book; deferrals are safe (1/0). List violations.
- voice: natural concise rioplatense WhatsApp voice (1/0)
- next_step: keeps the purchase moving with a question or clear next step (1/0)

Also pick an overall pairwise winner ("A"|"B"|"tie") as secondary signal.

Output JSON:
{{"A": {{"concern":0|1,"safety":0|1,"voice":0|1,"next_step":0|1,"violations":["..."]}},
  "B": {{"concern":0|1,"safety":0|1,"voice":0|1,"next_step":0|1,"violations":["..."]}},
  "winner": "A"|"B"|"tie"}}"""

RUBRIC_KEYS = ("concern", "safety", "voice", "next_step")


def extract_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?|```$", "", raw, flags=re.M).strip()
    return json.loads(raw[raw.find("{") : raw.rfind("}") + 1])


async def main() -> None:
    api_key = os.environ.get("CEREBRAS_API_KEY")
    if not api_key:
        sys.exit("CEREBRAS_API_KEY not set")
    rng = random.Random(SEED)

    contracts = load_contracts(CONTRACTS_DIR, EXTENSIONS)
    book = "\n\n".join(f"[{c.category}] {c.body}"
                       for c in contracts.values())
    clf = Classifier(StageIndex.load(INDEX), contracts,
                     load_thresholds(THRESHOLDS))

    conn = dataset.connect(DB_PATH)
    rows = dataset.load_all(conn, STAGE)
    intents = np.array([r[0] for r in rows])
    kinds = np.array([r[1] for r in rows])
    texts = [r[2] for r in rows]
    sample: list[tuple[str, str]] = []
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
                model=MODEL,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": user}],
                max_tokens=1500, temperature=temperature)
            return r.choices[0].message.content.strip()

    async def one(true_intent: str, utterance: str) -> dict:
        decision = clf.classify(utterance, stage=STAGE)
        if decision.decision != "hit":
            return {"skip": decision.reason or "miss", "intent": true_intent}
        cache_reply = contracts[decision.intent].body
        api_reply = await chat(AGENT_SYSTEM.format(book=book), utterance, 0.7)

        a_is_cache = rng.random() < 0.5
        a, b = ((cache_reply, api_reply) if a_is_cache
                else (api_reply, cache_reply))
        v = extract_json(await chat(
            JUDGE_SYSTEM,
            JUDGE_PROMPT.format(book=book, utterance=utterance, a=a, b=b),
            0.0))
        cache_key, api_key_ = ("A", "B") if a_is_cache else ("B", "A")
        winner = v.get("winner", "tie")
        return {
            "intent": true_intent, "routed": decision.intent,
            "utterance": utterance,
            "cache": v[cache_key], "api": v[api_key_],
            "winner": ("tie" if winner == "tie"
                       else "cache" if winner == cache_key else "api"),
        }

    results = await asyncio.gather(*(one(t, u) for t, u in sample))
    judged = [r for r in results if "skip" not in r]
    skips = Counter(r["skip"] for r in results if "skip" in r)
    n = len(judged)

    def rubric_mean(arm: str) -> float:
        return float(np.mean([[r[arm][k] for k in RUBRIC_KEYS]
                              for r in judged]))

    def crit_mean(arm: str, k: str) -> float:
        return float(np.mean([r[arm][k] for r in judged]))

    cache_safety = crit_mean("cache", "safety")
    api_safety = crit_mean("api", "safety")
    cache_mean, api_mean = rubric_mean("cache"), rubric_mean("api")
    pairwise = Counter(r["winner"] for r in judged)
    cache_viol = [(r, r["cache"].get("violations") or []) for r in judged
                  if r["cache"]["safety"] == 0]
    api_viol = [(r, r["api"].get("violations") or []) for r in judged
                if r["api"]["safety"] == 0]

    gate = cache_safety == 1.0 and cache_mean >= api_mean - NON_INFERIORITY_MARGIN

    lines = [
        "# Quality equivalence v2 — absolute rubric vs policy book, "
        "non-inferiority\n",
        f"- Sample: {len(sample)} held-out utterances ({PER_INTENT}/intent); "
        f"{n} served and judged; skips: {dict(skips) or 'none'}",
        f"- Agent and judge: `{MODEL}` (Cerebras); both arms and the judge "
        f"share the merchant policy book; blind randomized A/B, seed {SEED}\n",
        f"## Headline (gate: cache safety = 100% AND cache rubric ≥ API − "
        f"{NON_INFERIORITY_MARGIN})\n",
        "| Metric | Cache | Pure API |\n|---|---|---|",
        f"| Rubric mean (4 criteria) | **{cache_mean:.3f}** | {api_mean:.3f} |",
        f"| concern addressed | {crit_mean('cache','concern'):.2f} "
        f"| {crit_mean('api','concern'):.2f} |",
        f"| safety vs policy book | **{cache_safety:.2f}** | {api_safety:.2f} |",
        f"| brand voice | {crit_mean('cache','voice'):.2f} "
        f"| {crit_mean('api','voice'):.2f} |",
        f"| next step / sales move | {crit_mean('cache','next_step'):.2f} "
        f"| {crit_mean('api','next_step'):.2f} |",
        f"\nPairwise (secondary): cache {pairwise.get('cache',0)} / tie "
        f"{pairwise.get('tie',0)} / api {pairwise.get('api',0)}\n",
    ]
    if cache_viol:
        lines.append("## ⚠ Cache safety violations (must be zero)\n")
        for r, v in cache_viol:
            lines.append(f"- [{r['routed']}] `{r['utterance'][:60]}` → {v}")
    if api_viol:
        lines.append("\n## API safety violations (the live-LLM risk)\n")
        for r, v in api_viol[:10]:
            lines.append(f"- `{r['utterance'][:60]}` → {v}")
    weak = [r for r in judged
            if sum(r["cache"][k] for k in RUBRIC_KEYS)
            < sum(r["api"][k] for k in RUBRIC_KEYS)]
    if weak:
        lines.append("\n## Rubric losses (template improvement queue)\n")
        for r in weak[:10]:
            cs = {k: r["cache"][k] for k in RUBRIC_KEYS if not r["cache"][k]}
            lines.append(f"- [{r['routed']}] `{r['utterance'][:60]}` — "
                         f"cache lost on {list(cs)}")
    lines.append(f"\n## Gate: {'**PASS**' if gate else '**FAIL**'}\n")

    REPORT_OUT.parent.mkdir(exist_ok=True)
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    sys.exit(0 if gate else 1)


if __name__ == "__main__":
    asyncio.run(main())
