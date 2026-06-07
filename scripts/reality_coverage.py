#!/usr/bin/env python3
"""Reality coverage: the formal graph measured against REAL consumer data.

The user's correction, made measurable. Synthetic personas walk the
funnel we designed; real customers (COCO Shoes, 59 real WhatsApp
conversations, 444 user turns) do whatever they want — and what they
want is overwhelmingly POST-SALE SERVICE (order status, exchanges,
restock, shipping coordination), not the clean sales funnel.

This script runs every real user turn through the cache runtime,
stateful per conversation, and produces the artifact that was missing:
a VISIBLE coverage report — the $0-serve rate over real traffic,
decomposed by conversation TOPIC, with the uncovered subgraphs named
and ranked by how often real customers actually hit them.

It is the red team the user asked for: not invented attacks, real
behaviour, scored against the graph.

Usage: CEREBRAS_API_KEY=... uv run python scripts/reality_coverage.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

COCO = Path.home() / "Downloads" / "coco_shoes_training_dataset.jsonl"

from gaucho_cache import spend
from gaucho_cache.api import Domain
from gaucho_cache.cerebras import BatchClient

# the topic taxonomy a shoe e-commerce actually serves (from reading COCO)
TOPICS = [
    "greeting", "order_status", "exchange_return", "restock_availability",
    "shipping_coordination", "product_question", "purchase_intent",
    "payment_discount", "complaint_problem", "thanks_closing",
    "wholesale_b2b", "other",
]
LABEL_SYS = ("You label a customer WhatsApp message by topic for a shoe "
             "e-commerce. Output ONLY JSON {\"topic\": \"<one of the list>\"}.")
LABEL = """Topics: {topics}

Customer message: "{msg}"
(context — the previous store message was: "{ctx}")

Pick the single best topic."""


def load_turns():
    """[(conv_idx, turn_idx, prev_assistant, user_msg)] across all convs."""
    out = []
    for ci, line in enumerate(open(COCO)):
        msgs = json.loads(line)["messages"]
        prev = ""
        ti = 0
        for m in msgs:
            if m["role"] == "assistant":
                prev = m["content"]
            elif m["role"] == "user":
                out.append((ci, ti, prev, m["content"]))
                ti += 1
    return out


async def main() -> None:
    turns = load_turns()
    print(f"{len(turns)} real user turns from {COCO.name}\n")
    client = BatchClient("reality_coverage")
    rt = Domain.mattress_slice().runtime()   # the sales graph we have today

    # ---- run each turn through the cache, stateful per conversation -------
    sessions: dict[int, object] = {}
    served = miss = 0
    by_conv_state = {}
    results = []
    for ci, ti, prev, msg in turns:
        s = sessions.get(ci) or rt.session()
        sessions[ci] = s
        d = rt.reply([{"role": "user", "content": msg}], session=s)
        results.append((ci, msg, prev, d.served, d.intent, d.reason))
        if d.served:
            served += 1
        else:
            miss += 1

    # ---- topic-label every turn (batched) --------------------------------
    async def label(msg, ctx):
        try:
            v = await client.chat_json(LABEL_SYS, LABEL.format(
                topics=", ".join(TOPICS), msg=msg[:300], ctx=(ctx or "")[:200]),
                temperature=0.0)
            t = str(v.get("topic", "other")).strip()
            return t if t in TOPICS else "other"
        except Exception:
            return "other"

    labels = await asyncio.gather(*(label(m, p) for _ci, m, p, *_ in results))

    # ---- cross-tab: topic × served --------------------------------------
    topic_tot = defaultdict(int)
    topic_served = defaultdict(int)
    for (ci, msg, prev, sv, intent, reason), topic in zip(results, labels):
        topic_tot[topic] += 1
        if sv:
            topic_served[topic] += 1

    print(f"=== REALITY COVERAGE: cache vs {len(turns)} real customer turns ===")
    print(f"served at $0: {served}/{len(turns)} = {served/len(turns):.0%} | "
          f"forwarded to LLM: {miss}\n")
    print(f"{'topic':24s}{'real share':>12s}{'$0 served':>12s}")
    for t in sorted(topic_tot, key=lambda k: -topic_tot[k]):
        tot, sv = topic_tot[t], topic_served[t]
        print(f"{t:24s}{tot:>5d} ({tot/len(turns):>3.0%}){sv:>7d}/{tot} "
              f"({sv/max(1,tot):>3.0%})")

    # the missing subgraphs, ranked by how much real traffic they own
    print("\n=== UNCOVERED SUBGRAPHS (ranked by real frequency) ===")
    holes = sorted(((topic_tot[t]-topic_served[t], t) for t in topic_tot
                    if topic_tot[t]-topic_served[t] > 0), reverse=True)
    for n, t in holes:
        print(f"  {n:3d} turns  {t}")
    json.dump({"served": served, "total": len(turns),
               "topic_tot": dict(topic_tot), "topic_served": dict(topic_served)},
              open(REPO / "reports" / "reality_coverage.json", "w"), indent=1)
    print(f"\nledger ${spend.spent():.2f}")


if __name__ == "__main__":
    (REPO / "reports").mkdir(exist_ok=True)
    asyncio.run(main())
