#!/usr/bin/env python3
"""Generate the P0.5 slice dataset on Cerebras (PLAN.md §11).

Port of models-medical-evaluation/chapter_3_3_dense_variants.py:
- Claude CLI            → Cerebras gpt-oss-120b (OpenAI-compatible API)
- 10 detail levels ×10  → length(4) × register(3) × noise(2) × 4 paraphrases
- idempotent resume     → same missing-cells pattern, SQLite-backed

Per intent: 24 cells × 4 = 96 positives + 20 hard negatives.
10 intents ≈ 1.2k short generations, ~260 API calls.

Usage:
    CEREBRAS_API_KEY=... uv run python scripts/generate_variants.py
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from pathlib import Path

from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gaucho_cache import dataset
from gaucho_cache.contracts import load_contracts, load_intent_specs

REPO = Path(__file__).resolve().parent.parent
DB_PATH = REPO / "data" / "slice.sqlite"
INTENTS_YAML = REPO / "data" / "intents_slice.yaml"
CONTRACTS_DIR = (REPO.parent / "agentic-crm" / "merchants" / "laferia"
                 / "templates" / "objections")

MODEL = "gpt-oss-120b"
BASE_URL = "https://api.cerebras.ai/v1"
CONCURRENCY = 8

SYSTEM = (
    "You write realistic WhatsApp messages from Argentine customers "
    "shopping for a mattress at an online store. You output ONLY a JSON "
    "array, no prose, no markdown fences."
)


def positives_prompt(spec, cell, template_body: str) -> str:
    return f"""Customers at the OBJECTION stage of a sales chat express this concern:

INTENT: {spec.intent}
MEANING: {spec.meaning}

(For context, the shop's canned answer to this concern is: "{template_body[:300]}")

Write exactly {dataset.PARAPHRASES_PER_CELL} DIFFERENT customer messages in Argentine Spanish expressing this concern, all matching:
- Length: {dataset.LENGTH_LEVELS[cell.length_level]}
- Register: {dataset.REGISTERS[cell.register]}
- Spelling: {dataset.NOISE_LEVELS[cell.noise]}

Rules:
- Each message must clearly express the INTENT above and nothing else.
- Vary vocabulary and angle between the {dataset.PARAPHRASES_PER_CELL} messages.
- These are customer messages, never the shop's answer.
- Do not mention the intent name.

Output: a JSON array of {dataset.PARAPHRASES_PER_CELL} strings."""


def negatives_prompt(spec, confusable_meanings: dict[str, str]) -> str:
    conf_lines = "\n".join(
        f"- {name}: {meaning}" for name, meaning in confusable_meanings.items()
    ) or "- other: anything the shop's canned answer for the intent cannot safely answer"
    return f"""We train a classifier for this customer-objection intent:

INTENT: {spec.intent}
MEANING: {spec.meaning}

Write exactly {dataset.NEGATIVES_PER_INTENT} HARD NEGATIVES: WhatsApp messages in Argentine Spanish that share vocabulary or topic with this intent — a naive classifier would route them here — but that actually express something DIFFERENT, belonging to one of:
{conf_lines}
- other: a related but distinct concern none of the above covers

Mix lengths and registers (formal, neutral, rioplatense slang, some with typos).

Output: a JSON array of {dataset.NEGATIVES_PER_INTENT} objects, each
{{"text": "<message>", "actual_intent": "<one of: {", ".join(list(confusable_meanings) + ["other"])}>"}}"""


def extract_json(raw: str):
    """Tolerant JSON-array extraction (the medical repo needed this too)."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?|```$", "", raw, flags=re.M).strip()
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end == -1:
        raise ValueError(f"no JSON array in response: {raw[:120]!r}")
    return json.loads(raw[start : end + 1])


async def call(client: AsyncOpenAI, sem: asyncio.Semaphore, prompt: str,
               retries: int = 3):
    async with sem:
        for attempt in range(retries):
            try:
                resp = await client.chat.completions.create(
                    model=MODEL,
                    messages=[{"role": "system", "content": SYSTEM},
                              {"role": "user", "content": prompt}],
                    max_tokens=2000,
                    temperature=0.9,
                )
                return extract_json(resp.choices[0].message.content)
            except Exception as e:  # noqa: BLE001 — retry then surface
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)


async def main() -> None:
    api_key = os.environ.get("CEREBRAS_API_KEY")
    if not api_key:
        sys.exit("CEREBRAS_API_KEY not set")

    specs = load_intent_specs(INTENTS_YAML)
    contracts = load_contracts(CONTRACTS_DIR)
    meanings = {s.intent: s.meaning for s in specs}
    conn = dataset.connect(DB_PATH)
    client = AsyncOpenAI(api_key=api_key, base_url=BASE_URL)
    sem = asyncio.Semaphore(CONCURRENCY)
    tasks = []

    async def fill_cell(spec, cell):
        body = contracts[spec.intent].body
        texts = await call(client, sem, positives_prompt(spec, cell, body))
        texts = [str(t) for t in texts][: dataset.PARAPHRASES_PER_CELL]
        if len(texts) < dataset.PARAPHRASES_PER_CELL:
            raise ValueError(f"{spec.intent}/{cell}: got {len(texts)} variants")
        dataset.store_positives(conn, cell, texts)

    async def fill_negatives(spec):
        conf = {c: meanings[c] for c in spec.confusables if c in meanings}
        items = await call(client, sem, negatives_prompt(spec, conf))
        pairs = [(str(it["text"]), str(it.get("actual_intent", "other")))
                 for it in items][: dataset.NEGATIVES_PER_INTENT]
        dataset.store_negatives(conn, spec.stage, spec.intent, pairs)

    for spec in specs:
        cells = dataset.missing_positive_cells(conn, spec.stage, spec.intent)
        print(f"{spec.intent}: {len(cells)} positive cells missing, "
              f"{dataset.missing_negatives(conn, spec.stage, spec.intent)} negatives missing")
        tasks += [fill_cell(spec, c) for c in cells]
        if dataset.missing_negatives(conn, spec.stage, spec.intent) > 0:
            tasks.append(fill_negatives(spec))

    print(f"→ {len(tasks)} generation calls (concurrency {CONCURRENCY})")
    results = await asyncio.gather(*tasks, return_exceptions=True)
    failures = [r for r in results if isinstance(r, Exception)]
    for f in failures[:5]:
        print(f"  ✗ {f}", file=sys.stderr)

    print("\nFinal counts:")
    for intent, kind, n in dataset.counts(conn, "objection"):
        print(f"  {intent:28s} {kind:9s} {n}")
    if failures:
        sys.exit(f"{len(failures)} calls failed — re-run to fill gaps (idempotent)")
    print("✓ dataset complete")


if __name__ == "__main__":
    asyncio.run(main())
