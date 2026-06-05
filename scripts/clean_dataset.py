#!/usr/bin/env python3
"""Corpus QA pass: LLM-judge every variant's true label (batched Cerebras).

Round 1 of eval exposed generation label noise: positives expressing a
different intent than requested ("¿Tienen garantía?" generated under
brand_trust) and negatives labeled "other" that actually belong to a
slice intent ("cuotas sin interés" IS price). This is the corpus-side
counterpart of the medical repo's bidirectional-consistency check.

For every variant (positives AND negatives), a judge classifies the
text into one of the 10 slice intents, "other", or "ambiguous":
- positive judged == its intent      → keep
- positive judged != its intent      → relabel (judged_intent column)
- positive judged ambiguous          → drop (ambiguity is the miss path —
                                        such turns go to the LLM fallback
                                        at runtime, never to a template)
- negative: actual_intent := judged  (corrects "other" mislabels)

Batched: 20 variants per call → ~60 calls for the 1.2k corpus.

Usage: CEREBRAS_API_KEY=... uv run python scripts/clean_dataset.py
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gaucho_cache import dataset
from gaucho_cache.contracts import load_intent_specs

REPO = Path(__file__).resolve().parent.parent
DB_PATH = REPO / "data" / "slice.sqlite"
INTENTS_YAML = REPO / "data" / "intents_slice.yaml"
MODEL = "gpt-oss-120b"
BASE_URL = "https://api.cerebras.ai/v1"
BATCH = 20
CONCURRENCY = 8
STAGE = "objection"

JUDGE_SYSTEM = (
    "You classify WhatsApp messages from Argentine mattress-store "
    "customers into objection intents. Output ONLY JSON."
)


def judge_prompt(specs, batch: list[tuple[int, str]]) -> str:
    intent_lines = "\n".join(f"- {s.intent}: {s.meaning}" for s in specs)
    numbered = "\n".join(f"{i}. \"{text}\"" for i, (_id, text) in enumerate(batch))
    return f"""Intents:
{intent_lines}
- other: a real concern none of the intents above covers
- ambiguous: too short/vague to assign one intent without more context (e.g. a 2-word fragment that fits several intents)

Classify each message. Judge ONLY what the text itself expresses.

Messages:
{numbered}

Output: JSON array of {len(batch)} objects {{"i": <number>, "intent": "<label>"}}"""


def extract_json(raw: str):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?|```$", "", raw, flags=re.M).strip()
    start, end = raw.find("["), raw.rfind("]")
    return json.loads(raw[start : end + 1])


async def main() -> None:
    api_key = os.environ.get("CEREBRAS_API_KEY")
    if not api_key:
        sys.exit("CEREBRAS_API_KEY not set")

    specs = load_intent_specs(INTENTS_YAML)
    valid = {s.intent for s in specs} | {"other", "ambiguous"}
    conn = dataset.connect(DB_PATH)
    rows = conn.execute(
        "SELECT id, kind, intent, text FROM variants WHERE stage=?", (STAGE,)
    ).fetchall()

    client = AsyncOpenAI(api_key=api_key, base_url=BASE_URL)
    sem = asyncio.Semaphore(CONCURRENCY)

    async def judge_batch(batch: list[tuple[int, str]]) -> dict[int, str]:
        async with sem:
            for attempt in range(3):
                try:
                    r = await client.chat.completions.create(
                        model=MODEL,
                        messages=[{"role": "system", "content": JUDGE_SYSTEM},
                                  {"role": "user",
                                   "content": judge_prompt(specs, batch)}],
                        max_tokens=2000, temperature=0.0)
                    items = extract_json(r.choices[0].message.content)
                    out = {}
                    for it in items:
                        label = str(it["intent"]).strip()
                        if label in valid:
                            out[batch[int(it["i"])][0]] = label
                    if len(out) == len(batch):
                        return out
                except Exception:  # noqa: BLE001
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2 ** attempt)
            return {}

    pairs = [(r[0], r[3]) for r in rows]
    batches = [pairs[i : i + BATCH] for i in range(0, len(pairs), BATCH)]
    print(f"Judging {len(pairs)} variants in {len(batches)} batched calls …")
    judged_maps = await asyncio.gather(*(judge_batch(b) for b in batches))
    judged: dict[int, str] = {}
    for m in judged_maps:
        judged.update(m)

    stats = Counter()
    for _id, kind, intent, _text in rows:
        verdict = judged.get(_id)
        if verdict is None:
            stats["unjudged"] += 1
            continue
        if kind == "positive":
            if verdict == intent:
                stats["pos_confirmed"] += 1
            elif verdict == "ambiguous":
                conn.execute("UPDATE variants SET dropped=1 WHERE id=?", (_id,))
                stats["pos_dropped_ambiguous"] += 1
            elif verdict == "other":
                conn.execute("UPDATE variants SET dropped=1 WHERE id=?", (_id,))
                stats["pos_dropped_other"] += 1
            else:
                conn.execute("UPDATE variants SET judged_intent=? WHERE id=?",
                             (verdict, _id))
                stats["pos_relabeled"] += 1
        else:
            if verdict == intent:
                # A "hard negative" that actually IS the intent: not a
                # negative at all. Drop it from the negative pool.
                conn.execute("UPDATE variants SET dropped=1 WHERE id=?", (_id,))
                stats["neg_dropped_is_positive"] += 1
            else:
                conn.execute("UPDATE variants SET actual_intent=? WHERE id=?",
                             ("other" if verdict == "ambiguous" else verdict, _id))
                stats["neg_actual_updated"] += 1
    conn.commit()

    print("\nQA pass results:")
    for k, v in sorted(stats.items()):
        print(f"  {k:28s} {v}")
    print("\nPost-QA counts (active rows):")
    for intent, kind, n in conn.execute(
        """SELECT COALESCE(NULLIF(judged_intent,''),intent), kind, COUNT(*)
           FROM variants WHERE stage=? AND dropped=0
           GROUP BY 1,2 ORDER BY 1,2""", (STAGE,)):
        print(f"  {intent:28s} {kind:9s} {n}")


if __name__ == "__main__":
    asyncio.run(main())
