#!/usr/bin/env python3
"""Conversational regression probe — the 'perfect' gate.

A fixed, growing table of (utterance, expected_intent, must_serve)
covering: colloquial Argentine greetings/thanks, store curiosity, core
objections, and every should-refuse class (greeting+concern compounds,
two-concern compounds, payment boundary, bare acks, out-of-catalog).

Every defect found while playing with the demo becomes a row here
BEFORE it gets fixed — the conversational write-back loop. The gate is
100%: a single regression fails the build.

Usage: uv run python scripts/probe_conversation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gaucho_cache.classifier import Classifier, StageIndex, load_thresholds
from gaucho_cache.contracts import load_all_contracts

REPO = Path(__file__).resolve().parent.parent

# (utterance, expected_intent_or_None, must_serve)
# must_serve=False → any non-serve outcome passes (the miss path is correct);
# expected_intent is still checked when routing matters for a serve.
PROBES: list[tuple[str, str | None, bool]] = [
    # --- greetings: mainstream + colloquial -------------------------------
    ("hola", "greet", True),
    ("Hola!", "greet", True),
    ("buenas tardes", "greet", True),
    ("buen día!", "greet", True),
    ("Como va?", "greet", True),
    ("que tal?", "greet", True),
    ("como andas?", "greet", True),
    ("todo bien?", "greet", True),
    ("holis", "greet", True),
    ("qué hacés?", "greet", True),
    ("hola, como estas?", "greet", True),
    # --- real-world openers (COCO dataset patterns) -------------------------
    ("Holaaa", "greet", True),
    ("Hola chicas", "greet", True),
    ("Holiss como están?", "greet", True),
    ("Hola!! Cómo estás?", "greet", True),
    ("Buen día chicas", "greet", True),
    # --- thanks / farewells ------------------------------------------------
    ("gracias!", "thanks_goodbye", True),
    ("mil gracias, genial!", "thanks_goodbye", True),
    ("gracias capo", "thanks_goodbye", True),
    ("joya, gracias", "thanks_goodbye", True),
    ("chau!", "thanks_goodbye", True),
    ("nos vemos", "thanks_goodbye", True),
    ("hasta luego", "thanks_goodbye", True),
    ("ok gracias", "thanks_goodbye", True),
    # --- store curiosity ----------------------------------------------------
    ("que venden?", "what_do_you_sell", True),
    ("venden solo colchones?", "what_do_you_sell", True),
    # --- core objections (one per intent) ------------------------------------
    ("tiene garantia?", "warranty", True),
    ("envian a salta capital?", "shipping_zone", True),
    ("el envio cuanto demora?", "shipping_time", True),
    ("sos un bot?", "bot_skepticism", True),
    ("hay alguien real ahi?", "bot_skepticism", True),
    # --- salutation decomposition: greeting + servable concern ---------------
    ("hola, tiene garantia?", "warranty", True),
    ("buenas! envian a salta capital?", "shipping_zone", True),
    ("Holaaa sos un bot?", "bot_skepticism", True),
    ("buen día, el envio cuanto demora?", "shipping_time", True),
    # --- MUST REFUSE: greeting + concern compounds ---------------------------
    ("hola, cuanto sale el king?", None, False),
    ("hola, ¿tenés almohadas?", None, False),
    ("buenas, ¿hacen envíos y cuánto tardan?", None, False),
    # --- MUST REFUSE: two-concern compounds ----------------------------------
    ("precio y garantia?", None, False),
    ("si no me gusta lo devuelvo? y cuanto tarda en llegar?", None, False),
    ("¿cuánto tarda el envío y cómo es la devolución?", None, False),
    # --- MUST REFUSE: payment boundary ----------------------------------------
    ("¿puedo pagar con Mercado Pago?", None, False),
    ("¿aceptan efectivo al recibir?", None, False),
    # --- MUST REFUSE: bare acks (context-dependent) ---------------------------
    ("dale", None, False),
    ("ok", None, False),
    ("si", None, False),
    ("mmm", None, False),
    # --- MUST REFUSE: out of catalog ------------------------------------------
    ("¿venden sommiers?", None, False),
    ("¿tienen local para visitar?", None, False),
    # --- quality boundary: belongs to brand_trust, not what_do_you_sell -------
    ("¿venden colchones de calidad?", None, False),
    # --- real-world greeting+concern (must fall to the LLM lane) -------------
    ("Hola! Tenes el modelo king en blanco?", None, False),
    ("Hola buen dia! Te escribo para tramitar un cambio de mi pedido", None, False),
    ("Hola! Alguna novedad sobre mi pedido?", None, False),
]


def main() -> None:
    clf = Classifier(
        StageIndex.load(REPO / "index" / "slice-v1.npz"),
        load_all_contracts(REPO, REPO / "data" / "contract_extensions.yaml"),
        load_thresholds(REPO / "index" / "thresholds.json"))

    failures = []
    for text, want_intent, must_serve in PROBES:
        d = clf.classify(text, stage="objection")
        served = d.serve_eligible
        ok = (served == must_serve) and (
            not must_serve or want_intent is None or d.intent == want_intent)
        mark = "✓" if ok else "✗"
        print(f"{mark} {('SERVE' if served else d.reason or 'miss'):22s} "
              f"{d.intent:18s} s={d.score:.2f} | {text}")
        if not ok:
            failures.append(text)

    n = len(PROBES)
    print(f"\n{n - len(failures)}/{n} expected behaviors")
    if failures:
        print("REGRESSIONS:", failures)
        sys.exit(1)
    print("✓ conversational gate: PASS")


if __name__ == "__main__":
    main()
