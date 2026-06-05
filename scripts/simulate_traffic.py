#!/usr/bin/env python3
"""Independent traffic simulator — the battle-test corpus.

The slice eval's held-out variants share the generator prompts of the
training corpus, so they understate real-world difficulty. This
simulator produces traffic from an INDEPENDENT distribution: sampled
personas (region, age, mood, typing style) × concern scenarios,
including out-of-taxonomy concerns and compound messages at realistic
rates — the novelty mix a deployed bot actually faces.

Ground truth = the concern the persona was instructed to express.

Usage:
    CEREBRAS_API_KEY=... uv run python scripts/simulate_traffic.py \
        --wave 1 --messages 12000
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gaucho_cache import spend
from gaucho_cache.cerebras import BatchClient
from gaucho_cache.contracts import load_intent_specs

REPO = Path(__file__).resolve().parent.parent
DB_PATH = REPO / "data" / "slice.sqlite"
INTENTS_YAML = REPO / "data" / "intents_slice.yaml"
PER_CALL = 20

REGIONS = ["AMBA (Buenos Aires)", "Córdoba", "Rosario / Litoral",
           "Mendoza / Cuyo", "Tucumán / NOA", "Neuquén / Patagonia"]
AGES = ["19-25", "26-35", "36-50", "51-70"]
MOODS = ["apurado/a, quiere respuestas ya", "desconfiado/a, ya lo estafaron una vez",
         "amable y charlatán/a", "irritado/a, tuvo un mal día",
         "indeciso/a, pregunta mucho", "directo/a, pocas palabras"]
STYLES = ["escribe prolijo con tildes y signos",
          "todo minúsculas sin tildes, apurado",
          "abreviaciones pesadas (q, xq, tmb, bn) y typos",
          "mensajes largos tipo audio transcripto, sin puntuación",
          "usa emojis y signos repetidos!!!"]

# Realistic concern mix: the 10 intents + novelty the cache must NOT serve.
NOVELTY = [
    ("payment_method", "cómo pagar: Mercado Pago, efectivo contra entrega, "
     "tarjeta en cuotas del banco, puntos, transferencia desde otro banco"),
    ("off_topic", "algo que una mueblería no resuelve con la plantilla de "
     "objeciones: venden almohadas/sommiers/sábanas, horario del local, "
     "trabajo/empleo, factura A, mayorista"),
    ("compound", "DOS preocupaciones distintas en el mismo mensaje (ej: "
     "devolución Y tiempo de envío; precio Y garantía)"),
]
NOVELTY_RATE = 0.25  # 25% of traffic is out-of-taxonomy or compound

SYSTEM = ("You write hyper-realistic WhatsApp messages from Argentine "
          "customers talking to an online mattress store. Output ONLY a "
          "JSON array of strings.")


def batch_prompt(rng: random.Random, concern_key: str, concern_desc: str,
                 n: int) -> str:
    persona = (f"Persona: {rng.choice(AGES)} años, {rng.choice(REGIONS)}, "
               f"{rng.choice(MOODS)}; {rng.choice(STYLES)}.")
    return f"""{persona}

Esta persona está chateando con una tienda online de colchones (etapa de objeciones: ya vio productos, tiene una duda antes de comprar).

Preocupación a expresar: {concern_desc}

Escribí exactamente {n} mensajes DISTINTOS que esta persona podría mandar expresando esa preocupación. Variá largo (de 2 palabras a 25), vocabulario y ángulo. Mantené el estilo de escritura de la persona. Son mensajes del cliente, nunca de la tienda. No menciones la palabra clave "{concern_key}".

Output: JSON array de {n} strings."""


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute("""CREATE TABLE IF NOT EXISTS traffic (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        wave INTEGER NOT NULL,
        concern TEXT NOT NULL,
        persona TEXT NOT NULL,
        text TEXT NOT NULL,
        UNIQUE(wave, concern, persona, text))""")
    conn.commit()


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wave", type=int, required=True)
    ap.add_argument("--messages", type=int, default=12000)
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()
    seed = a.seed if a.seed is not None else 1000 + a.wave
    rng = random.Random(seed)

    specs = load_intent_specs(INTENTS_YAML)
    concerns = [(s.intent, s.meaning) for s in specs]
    conn = sqlite3.connect(DB_PATH)
    ensure_table(conn)

    existing = conn.execute(
        "SELECT COUNT(*) FROM traffic WHERE wave=?", (a.wave,)).fetchone()[0]
    todo = a.messages - existing
    if todo <= 0:
        print(f"wave {a.wave} already has {existing} messages — nothing to do")
        return
    n_calls = (todo + PER_CALL - 1) // PER_CALL
    print(f"wave {a.wave}: generating {todo} messages in {n_calls} batched "
          f"calls (seed {seed}); ledger at ${spend.spent():.2f}")

    client = BatchClient("traffic_sim")

    async def one_call(i: int) -> int:
        r = random.Random(seed * 100_000 + i)
        if r.random() < NOVELTY_RATE:
            key, desc = r.choice(NOVELTY)
        else:
            key, desc = r.choice(concerns)
        persona_sig = f"call{i}-s{seed}"
        try:
            texts = await client.chat_json(
                SYSTEM, batch_prompt(r, key, desc, PER_CALL),
                temperature=1.0)
        except spend.BudgetExceeded:
            raise
        except Exception as e:  # noqa: BLE001
            print(f"  ✗ call {i}: {e}", file=sys.stderr)
            return 0
        rows = [(a.wave, key, persona_sig, str(t)) for t in texts[:PER_CALL]]
        with_lock = conn  # sqlite, single thread via asyncio loop
        with_lock.executemany(
            "INSERT OR IGNORE INTO traffic (wave, concern, persona, text) "
            "VALUES (?,?,?,?)", rows)
        with_lock.commit()
        return len(rows)

    done = 0
    results = await asyncio.gather(*(one_call(i) for i in range(n_calls)),
                                   return_exceptions=True)
    budget_hit = any(isinstance(r, spend.BudgetExceeded) for r in results)
    done = sum(r for r in results if isinstance(r, int))
    total = conn.execute("SELECT COUNT(*) FROM traffic WHERE wave=?",
                         (a.wave,)).fetchone()[0]
    by = conn.execute(
        "SELECT concern, COUNT(*) FROM traffic WHERE wave=? GROUP BY 1 "
        "ORDER BY 2 DESC", (a.wave,)).fetchall()
    print(f"\nwave {a.wave}: +{done} stored, total {total}")
    for c, n in by:
        print(f"  {c:28s} {n}")
    print(f"ledger: ${spend.spent():.2f}")
    if budget_hit:
        sys.exit("BUDGET CAP reached — campaign stops")


if __name__ == "__main__":
    asyncio.run(main())
