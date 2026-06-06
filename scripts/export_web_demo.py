#!/usr/bin/env python3
"""Export the serving stack for the in-browser demo.

Writes web/demo-data.json: the embedding index (float16, base64),
per-intent thresholds, match contracts (audited/preconditions/body),
the rotation pools, and the tour scenarios. build_book.py inlines this
into index.html, so the report is a single self-contained file — the
reader's browser embeds queries with the same HF model
(Xenova/paraphrase-multilingual-mpnet-base-v2 via transformers.js) and
runs the identical compound predicate in JS. Zero servers, zero API.
"""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gaucho_cache.classifier import StageIndex, load_thresholds
from gaucho_cache.contracts import default_contracts_dir, load_all_contracts, load_contracts

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "web" / "demo-data.json"
WEB_MODEL = "Xenova/paraphrase-multilingual-mpnet-base-v2"

SCENARIOS = [
    ("👋 Hola", "Hola!"),
    ("¿Qué venden?", "que venden exactamente?"),
    ("Gracias y chau", "mil gracias, genial!"),
    ("Hit limpio: garantía", "tiene garantia?"),
    ("Hit: zona de envío", "envian a salta capital?"),
    ("Hit: demora, con lunfardo", "el envio cuanto demora?"),
    ("Hit: ¿hay alguien real?", "hay alguien real ahi?"),
    ("Frontera: Mercado Pago → miss", "¿puedo pagar con Mercado Pago?"),
    ("Compuesto: dos dudas → miss", "si no me gusta lo devuelvo? y cuanto tarda en llegar?"),
    ("Fuera de catálogo → miss", "¿venden sommiers?"),
    ("Precondición de stock → miss", "se agotó! puedo reservar uno?"),
    ("Cautela post-battle-test", "la garantia q onda?"),
]


def main() -> None:
    index = StageIndex.load(REPO / "index" / "slice-v1.npz")
    thresholds = load_thresholds(REPO / "index" / "thresholds.json")
    contracts = load_all_contracts(REPO,
                               REPO / "data" / "contract_extensions.yaml")
    variants = json.loads(
        (REPO / "data" / "template_variants.json").read_text(encoding="utf-8"))

    emb16 = index.embeddings.astype(np.float16)
    payload = {
        "model": WEB_MODEL,
        "dim": int(index.embeddings.shape[1]),
        "n": int(index.embeddings.shape[0]),
        "embeddings_f16_b64": base64.b64encode(emb16.tobytes()).decode(),
        "intents": index.intents.tolist(),
        "kinds": index.kinds.tolist(),
        "thresholds": {k: vars(v) for k, v in thresholds.items()},
        "contracts": {
            c.category: {
                "template_id": c.template_id,
                "audited": c.audited,
                "requires_state": list(c.required_state_fields),
            } for c in contracts.values()
        },
        "variants": variants,
        "scenarios": SCENARIOS,
        "compound_floor": 0.82,
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"✓ wrote {OUT} ({OUT.stat().st_size // 1024} KB, "
          f"{payload['n']} vectors, dim {payload['dim']})")


if __name__ == "__main__":
    main()
