#!/usr/bin/env python3
"""Red-team the funnel's first turns — the surface a human tester hits.

The user's one-shots were all early-conversation messages: openers,
answers to the bot's first questions, acks, casual follow-ups. This
sweep generates exactly that surface at scale (persona × turn-type),
then audits BOTH failure directions:

  - every SERVE is fit-judged against the template it would send
    (an awkward/wrong serve is worse than a miss — it lies or ignores)
  - every MISS is coverable-judged (template-fit two-step); coverable
    misses are ingested as positives (register='redteam')

Unfit serves are reported loudly and NOT auto-fixed: each one is either
a missing hard negative or a doctrine bug — human (or at least
deliberate) attention required.

Usage: CEREBRAS_API_KEY=... uv run python scripts/redteam_first_turns.py
"""
from __future__ import annotations

import asyncio
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from close_question_coverage import (FIT_PROMPT, FIT_SYS, insert_positives,
                                     judge_coverable, rebuild, serving_stack)
from gaucho_cache import spend
from gaucho_cache.cerebras import BatchClient
from gaucho_cache.contracts import load_all_contracts

DB_PATH = REPO / "data" / "slice.sqlite"
STAGE = "objection"

PERSONAS = [
    "apurada, escribe corto y con typos, sin puntuación",
    "mayor, formal, de usted, frases completas",
    "joven, emojis, abreviaciones (q, xq, tmb, bn)",
    "desconfiada, pregunta antes de dar datos",
    "charlatán, da contexto de más en cada mensaje",
]

# (key, generation brief, the literal bot turn the fit-judge sees as context)
TURN_TYPES = [
    ("opener", "their FIRST message opening the chat (may be a greeting, "
               "a greeting+question, or going straight to the point)",
     "(inicio de la conversación, el bot todavía no preguntó nada)"),
    ("answer_for_whom", 'their reply right after the bot asked "¿buscás algo '
                        'para vos o para otra persona?"',
     "¿buscás algo para vos o para otra persona?"),
    ("answer_sizing", 'their reply right after the bot asked for bed size '
                      '(1/2 plazas, queen, king) and sleeping position',
     "¿de qué tamaño es tu cama (1 plaza, 2 plazas, queen, king) y cómo "
     "dormís más — de costado, boca arriba o boca abajo?"),
    ("post_promise", 'their reply right after the bot said "te busco las '
                     'mejores opciones, dame un momento"',
     "En base a tu tamaño y cómo dormís te busco las mejores opciones — "
     "dame un momento y te muestro lo que más te conviene."),
    ("early_question", "an early question about shipping, warranty, returns, "
                       "prices, payment or the store itself",
     "(inicio de la conversación)"),
]

N_PER_CELL = 8


async def main() -> None:
    contracts = load_all_contracts(REPO, REPO / "data/contract_extensions.yaml")
    clf = serving_stack()
    client = BatchClient("redteam_first_turns")

    async def gen(persona: str, turn_key: str, turn_desc: str):
        for attempt in range(2):  # one malformed JSON must not kill the sweep
            try:
                msgs = await client.chat_json(
                    "You write realistic WhatsApp messages from Argentine "
                    "mattress-store customers. Output ONLY a JSON array of "
                    "strings (escape quotes properly, no trailing commas).",
                    f"Customer persona: {persona}.\nWrite {N_PER_CELL} distinct "
                    f"realistic messages: {turn_desc}. Rioplatense Spanish.",
                    temperature=0.95)
                return turn_key, [str(m) for m in msgs][:N_PER_CELL]
            except (ValueError, KeyError, TypeError, Exception) as e:  # noqa: BLE001
                if attempt == 1:
                    print(f"  (cell dropped after retry: {persona[:20]}/{turn_key}: {e})")
        return turn_key, []

    bot_turn = {k: q for k, _d, q in TURN_TYPES}
    cells = await asyncio.gather(*(gen(p, k, d)
                                   for p in PERSONAS for k, d, _q in TURN_TYPES))

    LAST_INTENT = {"opener": None, "answer_for_whom": "greet",
                   "answer_sizing": "answer_for_whom",
                   "post_promise": "answer_size_posture",
                   "early_question": None}
    serves: list[tuple[str, str, str]] = []   # (turn, msg, intent)
    misses: list[tuple[str, str]] = []        # (turn, msg)
    total = 0
    for turn_key, msgs in cells:
        for m in msgs:
            total += 1
            d = clf.classify(m, stage=STAGE,
                             last_bot_intent=LAST_INTENT.get(turn_key))
            if d.serve_eligible:
                serves.append((turn_key, m, d.intent))
            elif d.decision != "hit":
                misses.append((turn_key, m))

    # ---- audit serves: would the template fit? -----------------------------
    async def fit(turn: str, msg: str, intent: str):
        c = contracts[intent]
        v = await client.chat_json(
            FIT_SYS, FIT_PROMPT.format(
                answer=msg, question=bot_turn.get(turn, "(primeros turnos)"),
                template=c.body), temperature=0.0)
        verdict = (v or {}).get("verdict", "incomplete") if isinstance(v, dict) else "incomplete"
        return turn, msg, intent, verdict == "ok", (v or {}).get("reason", "") if isinstance(v, dict) else "", verdict

    fits = await asyncio.gather(*(fit(*s) for s in serves))
    unfit = [f for f in fits if not f[3]]

    # ---- judge misses: coverable? ------------------------------------------
    verdicts = await asyncio.gather(
        *(judge_coverable(client, contracts, bot_turn.get(t, "(primeros turnos)"), m)
          for t, m in misses))
    coverable = [(i, m) for (_t, m), i in zip(misses, verdicts) if i]
    n_new = insert_positives(coverable, clf=clf)

    print(f"\n=== red team: {total} messages "
          f"({len(PERSONAS)} personas × {len(TURN_TYPES)} turn types) ===")
    lying = [f for f in unfit if f[5] == "contradicts"]
    incomplete = [f for f in unfit if f[5] != "contradicts"]
    print(f"serves: {len(serves)} | contradicting serves: {len(lying)} | "
          f"incomplete serves: {len(incomplete)} "
          f"({len(incomplete)/max(1,len(serves)):.0%}, bound 35%)")
    for t, m, i, _ok, why, v in lying:
        print(f"  CONTRADICTS [{t}] {m!r} served {i}: {why[:90]}")
    for t, m, i, _ok, why, v in incomplete[:6]:
        print(f"  incomplete [{t}] {m!r} served {i}: {why[:80]}")
    print(f"misses: {len(misses)} | coverable (ingested {n_new}): "
          f"{len(coverable)} | correct LLM-lane: {len(misses) - len(coverable)}")
    for i, m in coverable[:12]:
        print(f"  closing: {m!r} → {i}")
    if n_new:
        rebuild()
    print(f"\nledger ${spend.spent():.2f}")
    # Gate: contradicting serves (the lying direction) must be ZERO.
    # Incomplete serves (right funnel step, unaddressed extra) are a
    # quality rate, bounded like closure: the LLM lane is their fix in
    # production, the fence file is their fix here.
    sys.exit(1 if (lying or len(incomplete) > 0.35 * max(1, len(serves))) else 0)


if __name__ == "__main__":
    asyncio.run(main())
