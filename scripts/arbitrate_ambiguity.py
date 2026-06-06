#!/usr/bin/env python3
"""Round-3 corpus curation: kill cross-intent duplicates and compound
messages; arbitrate boundary cases with sharpened intent definitions.

Round 2 showed the residual confident-wrongs are corpus pathologies,
not classifier failures:
- the same utterance generated under TWO intents ("¿Pierdo la promo?"
  → price AND out_of_stock_reservation; similarity 1.000)
- compound messages carrying two concerns ("si no encaja, ¿me
  devuelven el dinero?" = size_fit + return_policy)
- boundary cases where adjacent intents share vocabulary ("cambio si
  llega con fallas" sits on the warranty/return_policy edge)

Mechanism:
1. Local (free): embed active positives; flag cross-intent pairs with
   cosine ≥ DUP_T (near-duplicates under different labels).
2. Local (free): leave-one-out route every positive; flag disagreements
   (route != label).
3. Batched Cerebras arbitration of flagged items with BOUNDARY-aware
   definitions and an explicit compound→ambiguous rule.
   ambiguous/compound → dropped; confident relabel → judged_intent.

Usage: CEREBRAS_API_KEY=... uv run python scripts/arbitrate_ambiguity.py
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from openai import AsyncOpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gaucho_cache import dataset
from gaucho_cache.classifier import Embedder

REPO = Path(__file__).resolve().parent.parent
DB_PATH = REPO / "data" / "slice.sqlite"
MODEL = "gpt-oss-120b"
BASE_URL = "https://api.cerebras.ai/v1"
BATCH = 15
CONCURRENCY = 8
STAGE = "objection"
DUP_T = 0.93

# Sharpened, boundary-aware definitions (what round-2 errors taught us).
BOUNDARIES = """- price: cost, discounts, installments/cuotas, payment options, promo conditions. NOT price if the worry is losing a promo while waiting for restock (that is out_of_stock_reservation).
- size_fit: will the dimensions fit their bed frame/room. NOT size_fit if they also ask about returning/refunds (compound → ambiguous).
- firmness_doubt: too firm/too soft for their body or sleep style.
- brand_trust: is the store/brand legit, reviews, fear of scams.
- bot_skepticism: are they talking to a bot, demand a human.
- warranty: manufacturing defects, faults, item arrives broken/fails later — "falla", "roto", "se hunde".
- return_policy: returning/exchanging because they don't like it or changed their mind (NO defect involved). Defect/fault → warranty.
- shipping_time: WHEN an orderable item arrives, delays, deadlines. Restock timing → out_of_stock_reservation. Coverage of their area → shipping_zone.
- shipping_zone: WHETHER delivery reaches their location (town, CP, province).
- out_of_stock_reservation: restock timing, reserving a unit, keeping a promo while waiting.
- greet: opens the conversation (hola, buenas, como va, que tal, holis) with NO concern attached.
- thanks_goodbye: gratitude or farewell closing the chat (gracias, joya gracias, chau, nos vemos).
- what_do_you_sell: asks what the store offers in general (que venden, solo colchones?, que marcas).
- other: a real concern none of the above covers.
- ambiguous: fragment too vague to assign, OR a compound message carrying two or more distinct concerns.

Fragment rule (STRICT): for messages of 1-3 words, only assign an intent when NO other intent could plausibly fit ("¿precio?" → price is fine; "¿pierdo promo?" could be price OR out_of_stock_reservation → ambiguous; "¿cuándo vuelve?" could be restock OR a return → ambiguous).
Promo rule: a promo/discount question tied to reserving or waiting for restock → out_of_stock_reservation; promo/discount conditions in general → price; a bare promo fragment that could be either → ambiguous.
Payment rule: questions about payment METHODS or platforms (Mercado Pago, efectivo, tarjeta as a means, paying online, loyalty points) without an expense/discount/installment concern are NOT price and NOT brand_trust → other. price covers how much it costs and how to afford it (cuotas/discounts); brand_trust covers fear of scams, not payment logistics."""

JUDGE_SYSTEM = ("You are a strict data curator for a mattress-store "
                "objection classifier. Output ONLY JSON.")


def judge_prompt(batch: list[tuple[int, str]]) -> str:
    numbered = "\n".join(f"{i}. \"{t}\"" for i, (_id, t) in enumerate(batch))
    return f"""Intent definitions with boundaries:
{BOUNDARIES}

Rule: when in doubt between two intents, or the message has two concerns, answer "ambiguous". The corpus must only keep crystal-clear exemplars.

Messages:
{numbered}

Output: JSON array of {len(batch)} objects {{"i": <number>, "intent": "<label>"}}"""


def extract_json(raw: str):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?|```$", "", raw, flags=re.M).strip()
    return json.loads(raw[raw.find("[") : raw.rfind("]") + 1])


async def main() -> None:
    api_key = os.environ.get("CEREBRAS_API_KEY")
    if not api_key:
        sys.exit("CEREBRAS_API_KEY not set")

    conn = dataset.connect(DB_PATH)
    rows = conn.execute(
        """SELECT id, COALESCE(NULLIF(judged_intent,''), intent), text,
                  COALESCE(length_level, 9)
           FROM variants WHERE stage=? AND kind='positive' AND dropped=0""",
        (STAGE,),
    ).fetchall()
    ids = np.array([r[0] for r in rows])
    labels = np.array([r[1] for r in rows])
    texts = [r[2] for r in rows]
    length_levels = np.array([r[3] for r in rows])

    print(f"Embedding {len(texts)} active positives …")
    emb = Embedder().encode(texts)
    sims = emb @ emb.T
    np.fill_diagonal(sims, -1.0)

    flagged: set[int] = set()
    # 1. cross-intent near-duplicates → flag BOTH sides
    dup_a, dup_b = np.where(sims >= DUP_T)
    n_dups = 0
    for a, b in zip(dup_a, dup_b):
        if a < b and labels[a] != labels[b]:
            flagged.update((int(a), int(b)))
            n_dups += 1
    # 2. leave-one-out routing disagreement
    n_dis = 0
    for i in range(len(texts)):
        best_per_intent: dict[str, float] = {}
        for intent in np.unique(labels):
            m = labels == intent
            m[i] = False
            if m.any():
                best_per_intent[intent] = float(sims[i][m].max())
        route = max(best_per_intent, key=best_per_intent.get)
        if route != labels[i]:
            flagged.add(i)
            n_dis += 1
    # 3. every fragment, unconditionally — round-4 showed all residual
    #    confident-wrongs were 1-3 word fragments; they face the strict
    #    fragment rule.
    n_frag = 0
    for i in np.where(length_levels == 0)[0]:
        if int(i) not in flagged:
            flagged.add(int(i))
            n_frag += 1
    # 4. payment-vocabulary sweep (round-5 residuals): payment-method
    #    questions are out-of-taxonomy and must not hide in price /
    #    brand_trust exemplars.
    pay_rx = re.compile(r"\bpag[aoue]|mercado\s?pago|efectivo|tarjeta|"
                        r"transferencia|puntos\b", re.IGNORECASE)
    n_pay = 0
    for i in range(len(texts)):
        if int(i) not in flagged and pay_rx.search(texts[i]):
            flagged.add(int(i))
            n_pay += 1
    print(f"Flagged: {len(flagged)} ({n_dups} cross-intent dup pairs, "
          f"{n_dis} LOO disagreements, {n_frag} fragments, {n_pay} payment)")

    flagged_items = [(int(ids[i]), texts[i]) for i in sorted(flagged)]
    valid = set(np.unique(labels)) | {"other", "ambiguous"}

    client = AsyncOpenAI(api_key=api_key, base_url=BASE_URL)
    sem = asyncio.Semaphore(CONCURRENCY)

    async def judge(batch):
        async with sem:
            for attempt in range(3):
                try:
                    r = await client.chat.completions.create(
                        model=MODEL,
                        messages=[{"role": "system", "content": JUDGE_SYSTEM},
                                  {"role": "user", "content": judge_prompt(batch)}],
                        max_tokens=1500, temperature=0.0)
                    out = {}
                    for pos, it in enumerate(extract_json(
                            r.choices[0].message.content)):
                        try:
                            label = str(it.get("intent") or it.get("label") or "").strip()
                            idx = int(it.get("i", pos))
                            if label in valid and 0 <= idx < len(batch):
                                out[batch[idx][0]] = label
                        except (TypeError, ValueError, AttributeError):
                            continue
                    if out:
                        return out
                except Exception:  # noqa: BLE001
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2 ** attempt)
            return {}

    batches = [flagged_items[i : i + BATCH]
               for i in range(0, len(flagged_items), BATCH)]
    print(f"Arbitrating {len(flagged_items)} flagged positives in "
          f"{len(batches)} batched calls …")
    verdicts: dict[int, str] = {}
    for m in await asyncio.gather(*(judge(b) for b in batches)):
        verdicts.update(m)

    by_id = {int(ids[i]): labels[i] for i in range(len(ids))}
    stats = Counter()
    for vid, verdict in verdicts.items():
        current = by_id[vid]
        if verdict in ("ambiguous", "other"):
            conn.execute("UPDATE variants SET dropped=1 WHERE id=?", (vid,))
            stats[f"dropped_{verdict}"] += 1
        elif verdict != current:
            conn.execute("UPDATE variants SET judged_intent=? WHERE id=?",
                         (verdict, vid))
            stats["relabeled"] += 1
        else:
            stats["confirmed"] += 1
    conn.commit()

    print("\nArbitration results:")
    for k, v in sorted(stats.items()):
        print(f"  {k:20s} {v}")
    print("\nActive positives per intent:")
    for intent, n in conn.execute(
        """SELECT COALESCE(NULLIF(judged_intent,''),intent), COUNT(*)
           FROM variants WHERE stage=? AND kind='positive' AND dropped=0
           GROUP BY 1 ORDER BY 1""", (STAGE,)):
        print(f"  {intent:28s} {n}")


if __name__ == "__main__":
    asyncio.run(main())
