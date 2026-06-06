#!/usr/bin/env python3
"""Bootstrap-from-zero: a VIRGIN domain, any agent, watch the curve climb.

The proof the proxy demands: a dental-clinic receptionist agent this
repo has never seen — no corpus, no templates, no taxonomy. Patient
personas call through the LearningProxy → Cerebras. Cycle by cycle:

  cycle 1: pure shadow (cache empty) — 0% cached, everything forwards
  after each cycle: distill_traffic.py mines the logs into a domain
  pack; shadow-serving accrues agreement evidence; promoted templates
  start answering for $0.

Expected honest behavior: the curve climbs on the REUSABLE surface
(hours, address, insurances, prices, greetings) while bookings — which
contain per-patient specifics — keep forwarding forever. That is the
design, not a failure: cache the spine, rent the meat.

Usage: CEREBRAS_API_KEY=... uv run python scripts/run_bootstrap.py --cycles 4 --n 18
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from gaucho_cache import spend
from gaucho_cache.cerebras import BatchClient
from gaucho_cache.classifier import Classifier, StageIndex, load_thresholds
from gaucho_cache.contracts import MatchContract
from gaucho_cache.proxy import LearningProxy

DOMAIN = "recepcion"
DB = REPO / "data" / "proxy_traffic.sqlite"
PACK = REPO / "data" / "domains" / DOMAIN

RECEP = """Sos la recepcionista virtual de la Clínica Dental Sonrisa
(Buenos Aires) por WhatsApp. Cálida, concisa, voseo.
Datos fijos: horario lun-vie 9 a 18, sáb 9 a 13. Dirección: Av. Rivadavia
4520, Caballito. Obras sociales: OSDE, Swiss Medical, Galeno; también
particular. Limpieza dental: $40.000. Consulta de diagnóstico: gratis la
primera vez. Turnos: pedís nombre y franja preferida, y confirmás
"te anoto, te llega recordatorio por acá".
Nunca inventes datos fuera de estos."""

MOODS = ["apurada", "amable", "confundido", "directo"]
GOALS = [
    "preguntar el horario de atención y despedirte",
    "preguntar si atienden tu obra social (OSDE) y despedirte",
    "preguntar cuánto sale una limpieza dental y despedirte",
    "preguntar la dirección y cómo llegar, y despedirte",
    "sacar un turno para limpieza esta semana (dá tu nombre cuando te lo pidan)",
    "preguntar si la primera consulta es gratis y despedirte",
]

PATIENT = """Sos un paciente argentino escribiendo a una clínica dental
por WhatsApp. Humor: {mood}. Tu objetivo: {goal}.
Conversación:
{hist}
Respondé SOLO tu próximo mensaje (corto, natural). Si tu objetivo ya se
cumplió, despedite brevemente. Si ya te despediste, respondé exactamente FIN."""

AGREE_SYS = ("You compare a CACHED reply against the live agent's ACTUAL "
             'reply. Output ONLY JSON {"equivalent": true|false}.')
AGREE = """Customer: "{msg}"
CACHED candidate: "{cached}"
ACTUAL agent reply: "{actual}"
Is the CACHED candidate a correct and sufficient STANDALONE answer to the
customer's message — same facts as ACTUAL where they overlap, nothing
invented, same direction? It does NOT need to include context-specific
extras that ACTUAL added (a name, a booking confirmation); but if the
customer's message REQUIRED those specifics, answer false."""


def load_pack():
    if not (PACK / "index.npz").exists():
        return None, {}
    variants = json.loads((PACK / "variants.json").read_text())
    contracts = {i: MatchContract(template_id=f"{i.upper()}-auto", category=i,
                                  version=1, audited=True, body=v[0])
                 for i, v in variants.items()}
    clf = Classifier(StageIndex.load(PACK / "index.npz"), contracts,
                     load_thresholds(PACK / "thresholds.json"))
    return clf, variants


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=4)
    ap.add_argument("--n", type=int, default=18)
    ap.add_argument("--seed", type=int, default=3)
    a = ap.parse_args()

    client = BatchClient("bootstrap_recepcion")

    async def forward(messages):
        hist = "\n".join(f"{m['role']}: {m['content']}" for m in messages[1:])
        txt = await client.chat(RECEP, hist + "\nRespondé SOLO tu mensaje.",
                                temperature=0.6, max_tokens=400)
        return txt.strip(), 0.0

    async def agreement(msg, cached, actual):
        v = await client.chat_json(AGREE_SYS, AGREE.format(
            msg=msg, cached=cached, actual=actual), temperature=0.0)
        return 1.0 if (isinstance(v, dict) and v.get("equivalent")) else 0.0

    curve = []
    for cycle in range(1, a.cycles + 1):
        clf, variants = load_pack()
        proxy = LearningProxy(DOMAIN, forward, DB, classifier=clf,
                              variants=variants, mode="auto")
        c_cache = c_prov = 0

        async def conv(i):
            nonlocal c_cache, c_prov
            r = random.Random(a.seed * 100 + cycle * 1000 + i)
            mood, goal = r.choice(MOODS), GOALS[i % len(GOALS)]
            msgs = [{"role": "system", "content": "recepcion"}]
            hist_txt = ""
            for _t in range(4):
                p = (await client.chat(
                    "Output only the message.", PATIENT.format(
                        mood=mood, goal=goal, hist=hist_txt or "(inicio)"),
                    temperature=0.9, max_tokens=200)).strip()
                if not p or p.upper().startswith("FIN"):
                    break
                msgs.append({"role": "user", "content": p})
                hist_txt += f"\nVos: {p}"
                dec = await proxy.chat(msgs, agreement_judge=agreement)
                msgs.append({"role": "assistant", "content": dec.reply})
                hist_txt += f"\nClínica: {dec.reply}"
                if dec.served_by == "cache":
                    c_cache += 1
                else:
                    c_prov += 1
            return None

        await asyncio.gather(*(conv(i) for i in range(a.n)))
        total = c_cache + c_prov
        share = c_cache / max(1, total)
        curve.append((cycle, c_cache, c_prov, share))
        print(f"cycle {cycle}: {c_cache} cached / {c_prov} provider "
              f"= {share:.0%} cached")

        if cycle < a.cycles:
            r = subprocess.run(
                [sys.executable, str(REPO / "scripts" / "distill_traffic.py"),
                 "--domain", DOMAIN], capture_output=True, text=True)
            print("  " + (r.stdout.strip().splitlines() or ["(no distill)"])[-1])

    print("\n=== the curve (any agent, zero hand-written taxonomy) ===")
    for cycle, cc, cp, share in curve:
        print(f"  cycle {cycle}: {'█' * int(share * 40):<40} {share:.0%} "
              f"({cc}c/{cp}p)")
    print(f"ledger ${spend.spent():.2f}")


if __name__ == "__main__":
    asyncio.run(main())
