#!/usr/bin/env python3
"""Gym-style conversion eval: does the cache help or hurt the CLOSE?

Ported value function from agentic-crm's gym (gym/src/gym/runner.py):
  - Customer FSM: AIDA (awareness → interest → desire → action), ±1 per turn
  - Per-turn customer sentiment JSON: stage_in/stage_out,
    would_buy_now_if_offered, intent_to_continue, payment_method
  - CONVERSION TRIFECTA: would_buy AND stage_out==action AND payment
    captured (conversion-eligible method) AND the bot delivered the close
  - Outcome precedence: CONVERTED > LOST_INTEREST > TIMED_OUT

Two arms, same personas, same seeds:
  hybrid : cache (class A templates + class B catalog renders) + LLM lane
  control: pure LLM every turn (same sales brief, same catalog)

Gates: hybrid conversion rate >= control − 10pp (parity) AND zero
in-context bad cached serves. Reported: cached-turn share per stage of
the funnel — the number this iteration exists to move.

Usage: CEREBRAS_API_KEY=... uv run python scripts/gym_eval.py --n 24 --seed 7
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from gaucho_cache import spend
from gaucho_cache.cerebras import BatchClient
from gaucho_cache.classifier import Classifier, StageIndex, load_thresholds
from gaucho_cache.contracts import load_all_contracts
from gaucho_cache.render import catalog, ladder
from gaucho_cache.serving import BotState, serve_turn

DB_PATH = REPO / "data" / "slice.sqlite"
STAGES = ["awareness", "interest", "desire", "action"]
ELIGIBLE = {m["method_key"] for m in ladder() if m["conversion_eligible"]}

MOODS = ["apurado", "relajado", "desconfiado", "indeciso", "entusiasta"]
STYLES = ["voseo casual con typos", "formal de usted",
          "joven con emojis y abreviaciones", "seco y directo"]
GOALS = [
    ("buy_yes_yes", "Querés comprar HOY si te recomiendan un colchón que te "
     "sirva y te dan cuotas claras. Antes de pagar SIEMPRE preguntás precio "
     "y cuotas. Cuando un producto te convence y viste las formas de pago, "
     "elegís una (efectivo, débito, transferencia o cuotas) y lo decís."),
    ("buy_cautious", "Querés comprar pero sos cauteloso: hacés una objeción "
     "(garantía, envío o devolución) antes de decidir. Si la resuelven bien "
     "y el precio te cierra, elegís una forma de pago y comprás."),
    ("browse_maybe", "Estás mirando. Solo comprás si la atención es muy "
     "buena y hay una oferta que te tienta; si no, te despedís educadamente."),
]

CUST = """Sos un cliente argentino de WhatsApp en una tienda de colchones.
Humor: {mood}. Estilo: {style}.
Tu objetivo: {goal}
Tu cama es {size} y dormís {posture}.

Conversación hasta ahora:
{hist}

Respondé SOLO un JSON:
{{"message": "<tu próximo mensaje, corto y natural>",
 "stage_out": "awareness|interest|desire|action",
 "would_buy_now_if_offered": true|false,
 "intent_to_continue": true|false,
 "payment_method": null|"efectivo"|"debito"|"transferencia"|"cuotas_3"|"cuotas_6"}}

Reglas FSM (como el gym): tu etapa anterior era "{stage}"; stage_out puede
moverse A LO SUMO un paso. Pasás a "desire" cuando una recomendación
concreta te convence; a "action" cuando decidís comprar y elegís pago.
payment_method se setea SOLO cuando vos lo decís en el mensaje. Si ya no
te interesa, intent_to_continue=false y un mensaje de despedida."""

SALES = """Sos el vendedor estrella de La Feria del Colchón por WhatsApp
(voseo cálido, conciso). Catálogo (precios de lista; aplicá la escalera de
pagos cuando pidan precio):
{catalog}
Escalera de pagos: {ladder}
Tu trabajo: avanzar el funnel — entender medida y postura, recomendar 1-2
productos concretos con precio, ofrecer formas de pago, y CERRAR con un
link de checkout https://laferia.example/checkout/<SKU>?pago=<metodo>
cuando el cliente elige. Nunca inventes productos ni precios.

Conversación:
{hist}
Cliente: {msg}

Respondé SOLO el mensaje del vendedor."""

JUDGE = """Auditá las respuestas del CACHÉ (marcadas [CACHE]) en esta
conversación de venta. Una respuesta es MALA si contradice el contexto,
ignora una pregunta explícita del cliente, da información incorrecta del
catálogo, o apunta en la dirección equivocada (despedirse de quien quiere
comprar, etc.). Pedir el dato siguiente del funnel NO es malo.

{hist}

JSON: {{"bad_cache_turns": [{{"turn": <n>, "why": "..."}}], "conversation_ok": true|false}}"""


def load_variants() -> dict:
    return json.loads((REPO / "data" / "template_variants.json").read_text())


async def run_conv(client, clf, variants, arm: str, i: int, seed: int,
                   cat_brief: str, ladder_brief: str):
    r = random.Random(seed * 1000 + i)
    mood, style = r.choice(MOODS), r.choice(STYLES)
    goal_key, goal = GOALS[i % len(GOALS)]
    size = r.choice(["1 plaza", "2 plazas", "queen", "king"])
    posture = r.choice(["de costado", "boca arriba", "boca abajo"])
    state = BotState(salt=seed * 1000 + i)
    greet = variants["greet"][0]
    hist = [("bot", greet, "CACHE")]
    stage = "awareness"
    cached = llm = 0
    reasons: dict[str, int] = {}
    outcome, payment, delivered_close = "timed_out", None, False

    for turn in range(12):
        htxt = "\n".join(f"{'Tienda' if s == 'bot' else 'Cliente'}: {t}"
                         for s, t, _ in hist)
        try:
            cj = await client.chat_json(
                "Output ONLY the JSON.", CUST.format(
                    mood=mood, style=style, goal=goal, size=size,
                    posture=posture, hist=htxt, stage=stage),
                temperature=0.9, max_tokens=700)
        except Exception:
            break
        msg = str(cj.get("message", "")).strip()
        if not msg:
            break
        # clamp FSM ±1 like the gym
        so = str(cj.get("stage_out", stage))
        if so in STAGES and abs(STAGES.index(so) - STAGES.index(stage)) <= 1:
            stage = so
        hist.append(("cust", msg, ""))
        would_buy = bool(cj.get("would_buy_now_if_offered"))
        pm = cj.get("payment_method")
        if pm in ELIGIBLE:
            payment = pm

        if not cj.get("intent_to_continue", True):
            outcome = "lost_interest"
            break

        # ---- bot turn ----
        if arm == "hybrid":
            reply, lane, intent, reason = serve_turn(clf, variants, state, msg, r)
            if reply is None:
                reply = (await client.chat(
                    "Sé breve.", SALES.format(catalog=cat_brief,
                                              ladder=ladder_brief,
                                              hist=htxt, msg=msg),
                    temperature=0.7, max_tokens=600)).strip()
                lane = "LLM"; llm += 1
            else:
                cached += 1
                reasons[reason] = reasons.get(reason, 0) + 1
            if reason == "class_b_close":
                delivered_close = True
        else:
            reply = (await client.chat(
                "Sé breve.", SALES.format(catalog=cat_brief,
                                          ladder=ladder_brief,
                                          hist=htxt, msg=msg),
                temperature=0.7, max_tokens=600)).strip()
            lane = "LLM"; llm += 1
        if "checkout" in reply:
            delivered_close = True
        hist.append(("bot", reply, lane))

        # gym trifecta
        if would_buy and stage == "action" and payment and delivered_close:
            outcome = "converted"
            break

    # in-context judge over cached turns (hybrid arm only)
    bad = 0
    if arm == "hybrid" and cached:
        jh = "\n".join(f"{n}. {'Cliente' if s == 'cust' else f'Tienda [{l or 'LLM'}]'}: {t}"
                       for n, (s, t, l) in enumerate(hist))
        try:
            v = await client.chat_json("Output ONLY JSON.",
                                       JUDGE.format(hist=jh), temperature=0.0)
            bad = len(v.get("bad_cache_turns", []))
            if bad:
                con = sqlite3.connect(DB_PATH)
                for b in v.get("bad_cache_turns", []):
                    con.execute(
                        "INSERT INTO conv_failures (seed,conv,customer,cache_replied,why) "
                        "VALUES (?,?,?,?,?)",
                        (seed, i, f"gym:{goal_key}", str(b.get("turn", "")),
                         str(b.get("why", ""))[:300]))
                con.commit()
        except Exception:
            bad = -1
    return dict(arm=arm, goal=goal_key, outcome=outcome, turns=len(hist) // 2,
                cached=cached, llm=llm, bad=max(bad, 0), reasons=reasons)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--seed", type=int, default=7)
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
    client = BatchClient("gym_eval")

    res = await asyncio.gather(*(
        run_conv(client, clf, variants, arm, i, a.seed, cat_brief, ladder_brief)
        for arm in ("hybrid", "control") for i in range(a.n)))

    for arm in ("hybrid", "control"):
        rs = [r for r in res if r["arm"] == arm]
        conv = sum(1 for r in rs if r["outcome"] == "converted")
        lost = sum(1 for r in rs if r["outcome"] == "lost_interest")
        cached = sum(r["cached"] for r in rs)
        llm = sum(r["llm"] for r in rs)
        share = cached / max(1, cached + llm)
        bad = sum(r["bad"] for r in rs)
        agg: dict[str, int] = {}
        for r in rs:
            for k, v in r.get("reasons", {}).items():
                agg[k] = agg.get(k, 0) + v
        rtxt = ", ".join(f"{k}×{v}" for k, v in sorted(agg.items(), key=lambda kv: -kv[1]))
        print(f"{arm:8s}: {conv}/{len(rs)} converted ({conv/len(rs):.0%}) | "
              f"{lost} lost | cached share {share:.0%} "
              f"({cached}c/{llm}l) | bad cached serves: {bad}")
        if rtxt:
            print(f"          cached lanes: {rtxt}")
    h = [r for r in res if r["arm"] == "hybrid"]
    c = [r for r in res if r["arm"] == "control"]
    hc = sum(1 for r in h if r["outcome"] == "converted") / len(h)
    cc = sum(1 for r in c if r["outcome"] == "converted") / len(c)
    bad = sum(r["bad"] for r in h)
    ok = hc >= cc - 0.10 and bad == 0
    print(f"\nparity gate (hybrid ≥ control − 10pp): "
          f"{'✓ PASS' if ok else '✗ FAIL'} | ledger ${spend.spent():.2f}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
