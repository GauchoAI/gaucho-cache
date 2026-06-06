#!/usr/bin/env python3
"""The conversation-level Turing test: the whole sale, blind.

Chapter 10 tested single replies; a judge identified the canned one
78.5% of the time until variant rotation killed the tell. This is the
harder, final form of the user's goal — "perfect any conversation until
it really feels as if we are talking to cerebras directly" — measured
at the level that matters: ENTIRE sales conversations.

Protocol:
  1. Run matched pairs through the gym machinery: same persona, same
     seed — one conversation served by the hybrid (cache + LLM lane),
     one by pure LLM. Lane markers stripped.
  2. IDENTIFICATION: a judge sees one conversation, knows one of the
     two salesmen "uses cached/templated replies for part of its
     turns", and must say whether THIS conversation is the cached one,
     plus the tell that gave it away. Gate: accuracy ≈ chance
     (≤ 62.5% on n=48, the one-sided 95% binomial bound).
  3. PREFERENCE: a judge sees the matched pair side by side (A/B
     randomized) and picks the better salesman — rubric: warmth,
     concreteness, funnel progress, would-you-buy. Gate: hybrid
     preferred ≥ 45% (non-inferiority).

Usage: CEREBRAS_API_KEY=... uv run python scripts/turing_conversations.py --n 24 --seed 5
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from gaucho_cache import spend
from gaucho_cache.cerebras import BatchClient
from gaucho_cache.classifier import Classifier, StageIndex, load_thresholds
from gaucho_cache.contracts import load_all_contracts
from gaucho_cache.render import catalog, ladder
from gaucho_cache.serving import BotState, serve_turn

from gym_eval import (CUST, GOALS, MOODS, SALES, STAGES, STYLES,
                      load_variants)

IDENT = """Una de dos tiendas de colchones por WhatsApp usa un CACHÉ para
parte de sus respuestas (plantillas aprobadas y fichas de catálogo
pre-armadas); la otra genera todo con un LLM en vivo. Vas a ver UNA
conversación completa. Decidí si el vendedor de ESTA conversación es el
que usa caché.

{conv}

JSON: {{"cached": true|false, "confidence_0_10": <n>, "tell": "<qué te lo sugirió, en una frase>"}}"""

PREF = """Dos vendedores de colchones atendieron al MISMO cliente (misma
personalidad, mismo objetivo). Evaluá cuál vendió mejor: calidez,
concreción (productos y precios reales), avance del funnel, y si vos
le comprarías.

=== VENDEDOR A ===
{a}

=== VENDEDOR B ===
{b}

JSON: {{"better": "A"|"B", "why": "<una frase>"}}"""


async def run_pair(client, clf, variants, i: int, seed: int,
                   cat_brief: str, ladder_brief: str):
    """One persona, two salesmen. Returns (hybrid_txt, control_txt)."""
    r0 = random.Random(seed * 1000 + i)
    mood, style = r0.choice(MOODS), r0.choice(STYLES)
    goal_key, goal = GOALS[i % len(GOALS)]
    size = r0.choice(["1 plaza", "2 plazas", "queen", "king"])
    posture = r0.choice(["de costado", "boca arriba", "boca abajo"])

    async def one(arm: str):
        r = random.Random(seed * 1000 + i)  # same customer randomness
        state = BotState(salt=seed * 1000 + i)
        hist = [("bot", variants["greet"][0])]
        stage = "awareness"
        for _ in range(10):
            htxt = "\n".join(f"{'Tienda' if s == 'bot' else 'Cliente'}: {t}"
                             for s, t in hist)
            try:
                cj = await client.chat_json(
                    "Output ONLY the JSON.", CUST.format(
                        mood=mood, style=style, goal=goal, size=size,
                        posture=posture, hist=htxt, stage=stage),
                    temperature=0.9, max_tokens=700)
            except Exception:
                break
            msg = str(cj.get("message", "")).strip()
            if not msg or not cj.get("intent_to_continue", True):
                break
            so = str(cj.get("stage_out", stage))
            if so in STAGES and abs(STAGES.index(so) - STAGES.index(stage)) <= 1:
                stage = so
            hist.append(("cust", msg))
            if arm == "hybrid":
                reply, lane, _i, _re = serve_turn(clf, variants, state, msg, r)
                if reply is None:
                    reply = (await client.chat(
                        "Sé breve.", SALES.format(
                            catalog=cat_brief, ladder=ladder_brief,
                            hist=htxt, msg=msg),
                        temperature=0.7, max_tokens=600)).strip()
            else:
                reply = (await client.chat(
                    "Sé breve.", SALES.format(
                        catalog=cat_brief, ladder=ladder_brief,
                        hist=htxt, msg=msg),
                    temperature=0.7, max_tokens=600)).strip()
            hist.append(("bot", reply))
            if "checkout" in reply and stage == "action":
                break
        return "\n".join(f"{'Tienda' if s == 'bot' else 'Cliente'}: {t}"
                         for s, t in hist)

    h, c = await asyncio.gather(one("hybrid"), one("control"))
    return h, c


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--seed", type=int, default=5)
    a = ap.parse_args()

    contracts = load_all_contracts(REPO, REPO / "data/contract_extensions.yaml")
    clf = Classifier(StageIndex.load(REPO / "index/slice-v1.npz"), contracts,
                     load_thresholds(REPO / "index/thresholds.json"))
    variants = load_variants()
    cat_brief = "\n".join(
        f"- {p['name']} | {p['size']} | {p['firmeza']} | {p['tecnologia']} | "
        f"lista ${p['price']:,} | SKU {p['sku']}"
        for p in catalog()["products"])
    ladder_brief = "; ".join(f"{m['label']} (x{m['multiplier']})"
                             for m in ladder())
    client = BatchClient("turing_conversations")

    pairs = await asyncio.gather(*(
        run_pair(client, clf, variants, i, a.seed, cat_brief, ladder_brief)
        for i in range(a.n)))

    # ---- identification (each conversation judged alone) -------------------
    convs = [(h, True) for h, _ in pairs] + [(c, False) for _, c in pairs]
    async def ident(conv, is_cached):
        try:
            v = await client.chat_json("Output ONLY JSON.",
                                       IDENT.format(conv=conv), temperature=0.0)
            return bool(v.get("cached")) == is_cached, str(v.get("tell", ""))[:90]
        except Exception:
            return None, ""
    iv = await asyncio.gather(*(ident(c, k) for c, k in convs))
    valid = [x for x in iv if x[0] is not None]
    correct = sum(1 for ok, _ in valid if ok)
    acc = correct / max(1, len(valid))

    # ---- preference (matched pairs, order randomized) -----------------------
    rr = random.Random(a.seed)
    async def pref(h, c):
        flip = rr.random() < 0.5
        A, B = (c, h) if flip else (h, c)
        try:
            v = await client.chat_json("Output ONLY JSON.",
                                       PREF.format(a=A, b=B), temperature=0.0)
            pick = str(v.get("better", "")).strip().upper()
            hybrid_won = (pick == "B") if flip else (pick == "A")
            return hybrid_won, str(v.get("why", ""))[:90]
        except Exception:
            return None, ""
    pv = await asyncio.gather(*(pref(h, c) for h, c in pairs))
    pvalid = [x for x in pv if x[0] is not None]
    wins = sum(1 for w, _ in pvalid if w)
    wr = wins / max(1, len(pvalid))

    print(f"\nIDENTIFICATION: {correct}/{len(valid)} = {acc:.0%} "
          f"(chance 50%; gate ≤ 62.5%)")
    tells = [t for ok, t in valid if not ok and t][:5]
    for t in [t for ok, t in valid if ok and t][:6]:
        print(f"  tell (correct guess): {t}")
    print(f"PREFERENCE: hybrid preferred {wins}/{len(pvalid)} = {wr:.0%} "
          f"(gate ≥ 45%)")
    for w, why in pvalid[:6]:
        print(f"  {'hybrid' if w else 'control'} won: {why}")
    ok = acc <= 0.625 and wr >= 0.45
    print(f"\n{'✓ TURING PASS' if ok else '✗ TURING FAIL'}; "
          f"ledger ${spend.spent():.2f}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
