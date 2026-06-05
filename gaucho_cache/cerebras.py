"""Shared batched Cerebras client: retries, JSON extraction, spend ledger.

Every campaign script goes through `BatchClient` so actual token usage
lands in the spend ledger (gaucho_cache.spend) and the budget guard
applies uniformly.
"""

from __future__ import annotations

import asyncio
import json
import os
import re

from openai import AsyncOpenAI

from . import spend

BASE_URL = "https://api.cerebras.ai/v1"
MODEL = "gpt-oss-120b"


def extract_json(raw: str):
    """Tolerant JSON extraction: strips fences, finds outermost [] or {}."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?|```$", "", raw, flags=re.M).strip()
    for open_, close in (("[", "]"), ("{", "}")):
        s, e = raw.find(open_), raw.rfind(close)
        if s != -1 and e > s:
            return json.loads(raw[s : e + 1])
    raise ValueError(f"no JSON in response: {raw[:120]!r}")


class BatchClient:
    def __init__(self, activity: str, concurrency: int = 16):
        api_key = os.environ.get("CEREBRAS_API_KEY")
        if not api_key:
            raise SystemExit("CEREBRAS_API_KEY not set")
        self.activity = activity
        self.client = AsyncOpenAI(api_key=api_key, base_url=BASE_URL)
        self.sem = asyncio.Semaphore(concurrency)

    async def chat(self, system: str, user: str, *, temperature: float = 0.7,
                   max_tokens: int = 4000, retries: int = 3) -> str:
        async with self.sem:
            for attempt in range(retries):
                try:
                    r = await self.client.chat.completions.create(
                        model=MODEL,
                        messages=[{"role": "system", "content": system},
                                  {"role": "user", "content": user}],
                        max_tokens=max_tokens, temperature=temperature)
                    u = r.usage
                    spend.record(self.activity,
                                 u.prompt_tokens if u else 0,
                                 u.completion_tokens if u else 0)
                    return r.choices[0].message.content.strip()
                except spend.BudgetExceeded:
                    raise
                except Exception:  # noqa: BLE001 — retry then surface
                    if attempt == retries - 1:
                        raise
                    await asyncio.sleep(2 ** attempt)
        raise RuntimeError("unreachable")

    async def chat_json(self, system: str, user: str, **kw):
        return extract_json(await self.chat(system, user, **kw))
