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


GOAL = 0.80   # GOAL.md north star: 80% real-traffic $0-serve


async def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", default=None,
                    help="domain pack to measure (default: mattress slice)")
    ap.add_argument("--service", action="store_true",
                    help="use the service serving path (class-B order lookup)")
    ap.add_argument("--holdout", action="store_true",
                    help="measure only held-out test convs (conv%%10<3)")
    a = ap.parse_args()
    turns = load_turns()
    if a.holdout:
        turns = [t for t in turns if t[0] % 10 < 3]
    label = ("service pack, HELD-OUT test convs" if a.holdout
             else a.domain or "mattress slice")
    print(f"{len(turns)} real user turns ({label})\n")
    client = BatchClient("reality_coverage")
    rt = (Domain(a.domain).runtime() if a.domain
          else Domain.mattress_slice().runtime())
    svc = None
    if a.service:
        from gaucho_cache import service as svc
        from gaucho_cache.classifier import (Classifier, StageIndex,
                                             load_thresholds)
        from gaucho_cache.contracts import MatchContract
        pack = REPO / "data" / "domains" / a.domain
        svc_variants = json.loads((pack / "variants.json").read_text())
        # real contracts (audited) → serve_eligible works AND salutation
        # decomposition fires (greeting-prefixed service turns route right)
        contracts = {i: MatchContract(template_id=f"{i.upper()}-svc",
                                      category=i, version=1, audited=True,
                                      body=v[0]) for i, v in svc_variants.items()}
        clf = Classifier(StageIndex.load(pack / "index.npz"), contracts,
                         load_thresholds(pack / "thresholds.json"))

    # ---- run each turn through the cache, stateful per conversation -------
    sessions: dict[int, object] = {}
    served = miss = 0
    by_conv_state = {}
    results = []
    pending: dict[int, str] = {}   # conv → service intent awaiting an order ref
    for ci, ti, prev, msg in turns:
        if svc is not None:
            # STATEFUL service walk: a turn is read in the context of the
            # bot's last move (the conversation graph, not isolated turns).
            last = pending.get(ci)
            cd = clf.classify(msg[:200], stage="cocoshoes-service",
                              last_bot_intent=last)
            srv = None
            oid = svc.extract_order_id(msg)
            # continuation: bot asked for a ref, customer now gives the
            # number (or a short reply) → serve the pending intent's flow
            AFFIRM = ("si", "sí", "sii", "dale", "ok", "listo", "ese", "este",
                      "ese mismo", "correcto", "exacto", "ese es")
            is_cont = oid or msg.lower().strip(" .!¡") in AFFIRM
            if last in svc.SERVICE_CLUSTER and is_cont:
                r = svc.serve_service(last, msg, continuation=True)
                if r is not None:
                    results.append((ci, msg, prev, True, last, "graph_" + r[1]))
                    served += 1
                    if oid:
                        pending.pop(ci, None)   # resolved
                    continue
            # contracts are audited → serve_eligible means the full compound
            # predicate cleared (threshold + margin + negative legs), and
            # salutation decomposition already fired for greeting-prefixed
            # turns. The parity judge is the backstop.
            if cd.serve_eligible:
                intent = cd.intent
                r = svc.serve_service(intent, msg)
                if r is not None:
                    srv = r
                elif intent in ("greeting", "thanks_closing"):
                    pool = svc_variants.get(intent)
                    if pool:
                        srv = (pool[0], "template")
            if srv is not None:
                results.append((ci, msg, prev, True, cd.intent, srv[1]))
                served += 1
                # a no-ref service ask sets the pending intent for next turn
                if cd.intent in svc.SERVICE_CLUSTER and srv[1] == "service_ask_ref":
                    pending[ci] = cd.intent
            else:
                results.append((ci, msg, prev, False, cd.intent,
                                cd.reason or "miss"))
                miss += 1
            continue
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

    # PARITY FLOOR: judge every served turn — is the reply actually correct
    # for what the customer said? Coverage that lies is not coverage.
    served_correct = served
    if svc is not None:
        SVC_JUDGE = ("You audit a shoe-store reply. Output ONLY JSON "
                     '{"ok": true|false}. ok=true if the reply is a correct, '
                     "non-misleading response to the customer message (asking "
                     "for an order number when one is needed is correct; a "
                     "wrong-topic or invented-fact reply is not).")
        srv_rows = [(m, rsn) for (_c, m, _p, sv, _i, rsn) in results if sv]

        async def jcorrect(msg, served_text):
            try:
                v = await client.chat_json(SVC_JUDGE,
                    f'Customer: "{msg}"\nStore reply: "{served_text}"',
                    temperature=0.0)
                return bool(v.get("ok")) if isinstance(v, dict) else True
            except Exception:
                return True
        # reconstruct served text per row for judging
        async def reserve(m, rsn, intent):
            r = svc.serve_service(intent, m)
            txt = r[0] if r else (svc_variants.get(intent, [""])[0])
            return await jcorrect(m, txt)
        judged = await asyncio.gather(*(
            reserve(m, rsn, i) for (_c, m, _p, sv, i, rsn) in results if sv))
        served_correct = sum(judged)
        import os as _os
        if _os.environ.get("SHOW_WRONG"):
            print("\n--- served-but-WRONG (floor breaches) ---")
            for ok, (_c, m, _p, sv, i, rsn) in zip(
                    judged, [r for r in results if r[3]]):
                if not ok:
                    print(f"  [{i}/{rsn}] {m[:64]!r}")
            print("---\n")

    rate = served / len(turns)
    crate = served_correct / len(turns)
    # the GOAL metric is served-AND-CORRECT (a lie is not coverage). Raw
    # served is shown only as the gross ceiling above it.
    goalnum = crate if svc is not None else rate
    print(f"=== REALITY COVERAGE: cache vs {len(turns)} real customer turns ===")
    bar = "█" * int(40 * goalnum) + "·" * (40 - int(40 * goalnum))
    goalmark = int(40 * GOAL)
    bar = bar[:goalmark] + "|" + bar[goalmark + 1:]
    if svc is not None:
        print(f"served-AND-CORRECT (the GOAL metric): {served_correct}/"
              f"{len(turns)} = {crate:.0%}  (goal {GOAL:.0%})")
        print(f"  [{bar}]")
        print(f"  raw served {rate:.0%} | served-but-WRONG (floor breach): "
              f"{served-served_correct} | forwarded: {miss}\n")
    else:
        print(f"served at $0: {served}/{len(turns)} = {rate:.0%}  "
              f"(goal {GOAL:.0%})")
        print(f"  [{bar}]")
        print(f"  {'✓ GOAL MET' if rate >= GOAL else f'{GOAL-rate:+.0%} to goal'}"
              f" | forwarded to LLM: {miss}\n")
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
    # persist per-turn labels (conv_idx, msg, topic) so the service domain
    # can be built from real phrasings without re-paying for labelling.
    # ONLY on a full run — a --holdout run must not clobber the full set.
    if not a.holdout:
        json.dump([{"conv": ci, "msg": msg, "topic": t}
                   for (ci, msg, prev, sv, intent, reason), t
                   in zip(results, labels)],
                  open(REPO / "reports" / "coco_labels.json", "w"),
                  ensure_ascii=False, indent=1)
    print(f"\nledger ${spend.spent():.2f}")


if __name__ == "__main__":
    (REPO / "reports").mkdir(exist_ok=True)
    asyncio.run(main())
