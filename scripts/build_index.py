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
import os as _os
OUT = REPO / "index" / _os.environ.get("GAUCHO_INDEX", "slice-v1.npz")
STAGE = _os.environ.get("GAUCHO_STAGE", "objection")


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

    import json, re, unicodedata
    def norm(t):
        t = unicodedata.normalize("NFKD", t.lower())
        return re.sub(r"[^a-z0-9ñ ]+", "", t).strip()
    cur = {norm(r[0]): r[1] for r in conn.execute(
        """SELECT text, COALESCE(NULLIF(judged_intent,''),intent) FROM variants
           WHERE stage=? AND kind='positive' AND dropped=0 AND register='curated'""",
        (STAGE,))}
    (REPO / "data" / "curated_exact.json").write_text(
        json.dumps(cur, ensure_ascii=False))
    OUT.parent.mkdir(exist_ok=True)
    StageIndex(emb, intents, kinds, actuals).save(OUT)
    n_pos = int((kinds == "positive").sum())
    print(f"✓ wrote {OUT} ({n_pos} positives, {len(texts) - n_pos} negatives, "
          f"dim {emb.shape[1]})")


if __name__ == "__main__":
    main()
