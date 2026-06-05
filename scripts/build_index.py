#!/usr/bin/env python3
"""Build the slice embedding index: data/slice.sqlite → index/slice-v1.npz."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gaucho_cache import dataset
from gaucho_cache.classifier import DEFAULT_MODEL, Embedder, StageIndex

REPO = Path(__file__).resolve().parent.parent
DB_PATH = REPO / "data" / "slice.sqlite"
OUT = REPO / "index" / "slice-v1.npz"
STAGE = "objection"


def main() -> None:
    conn = dataset.connect(DB_PATH)
    rows = dataset.load_all(conn, STAGE)
    if not rows:
        sys.exit("no variants in dataset — run scripts/generate_variants.py first")

    intents = np.array([r[0] for r in rows])
    kinds = np.array([r[1] for r in rows])
    texts = [r[2] for r in rows]
    actuals = np.array([r[3] for r in rows])

    print(f"Embedding {len(texts)} variants with {DEFAULT_MODEL} …")
    emb = Embedder().encode(texts)

    OUT.parent.mkdir(exist_ok=True)
    StageIndex(emb, intents, kinds, actuals).save(OUT)
    n_pos = int((kinds == "positive").sum())
    print(f"✓ wrote {OUT} ({n_pos} positives, {len(texts) - n_pos} negatives, "
          f"dim {emb.shape[1]})")


if __name__ == "__main__":
    main()
