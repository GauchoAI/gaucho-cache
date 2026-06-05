#!/usr/bin/env python3
"""Seed human-curated boundary negatives — the hand-authored layer of
sales intelligence.

Hard negatives are calibration data, and the highest-value ones are the
short ambiguous fragments real customers actually type on the intent
boundaries the eval exposed (defect-vs-preference, payment-method
questions). These are cheap to author by hand and idempotent to seed.

A fragment listed here under intent X (with its true home in
actual_intent) raises X's calibrated threshold exactly where X lies:
"q pasa falla?" as a return_policy negative means a defect fragment can
no longer be confidently served the return template.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gaucho_cache import dataset

REPO = Path(__file__).resolve().parent.parent
DB_PATH = REPO / "data" / "slice.sqlite"
STAGE = "objection"

# (owner_intent, text, actual_intent)
CURATED: list[tuple[str, str, str]] = [
    # defect fragments must not serve the return-policy template
    ("return_policy", "q pasa falla?", "warranty"),
    ("return_policy", "¿y si llega fallado?", "warranty"),
    ("return_policy", "si sale con falla q hago", "warranty"),
    ("return_policy", "llega roto, ¿qué hago?", "warranty"),
    ("return_policy", "¿y si tiene un defecto de fábrica?", "warranty"),
    ("return_policy", "se hunde a los meses, ¿qué pasa?", "warranty"),
    # preference returns must not serve the warranty template
    ("warranty", "no me gustó, ¿lo devuelvo?", "return_policy"),
    ("warranty", "¿puedo cambiarlo si no me convence?", "return_policy"),
    ("warranty", "me arrepentí, ¿qué hago?", "return_policy"),
    ("warranty", "¿devolución si no me gusta?", "return_policy"),
    # payment-method logistics must not serve the price template
    ("price", "¿puedo pagar con Mercado Pago?", "other"),
    ("price", "¿aceptan efectivo?", "other"),
    ("price", "pago x internet?", "other"),
    ("price", "¿se puede pagar al recibir?", "other"),
    ("price", "¿suman puntos del programa de fidelidad?", "other"),
    # restock fragments must not serve shipping_time
    ("shipping_time", "cuando reponen?", "out_of_stock_reservation"),
    ("shipping_time", "¿cuándo vuelve a haber stock?", "out_of_stock_reservation"),
    # in-stock delivery fragments must not serve out_of_stock
    ("out_of_stock_reservation", "cuanto tarda el envio?", "shipping_time"),
    ("out_of_stock_reservation", "¿llega esta semana si pido hoy?", "shipping_time"),
]


def main() -> None:
    conn = dataset.connect(DB_PATH)
    seeded = 0
    for owner, text, actual in CURATED:
        exists = conn.execute(
            """SELECT 1 FROM variants WHERE stage=? AND intent=? AND
               kind='negative' AND text=?""", (STAGE, owner, text),
        ).fetchone()
        if exists:
            continue
        start = dataset.next_negative_index(conn, STAGE, owner)
        dataset.store_negatives(conn, STAGE, owner, [(text, actual)],
                                start_index=start)
        seeded += 1
    print(f"✓ seeded {seeded} curated boundary negatives "
          f"({len(CURATED) - seeded} already present)")


if __name__ == "__main__":
    main()
