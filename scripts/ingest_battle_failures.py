#!/usr/bin/env python3
"""Write-back loop: confirmed battle failures become hard negatives.

Every judge-confirmed wrong serve from battle_eval is real-world
calibration gold: a message that fooled the served intent. Ingesting it
as that intent's hard negative (actual_intent = the judge's true label)
raises the intent's calibrated threshold and negative-margin exactly
where it lied. Idempotent — rows are marked ingested.

After ingesting: rebuild the index and recalibrate
(scripts/build_index.py + scripts/eval_slice.py).
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gaucho_cache import dataset

REPO = Path(__file__).resolve().parent.parent
DB_PATH = REPO / "data" / "slice.sqlite"
STAGE = "objection"


def main() -> None:
    conn = dataset.connect(DB_PATH)
    rows = conn.execute(
        """SELECT traffic_id, text, served_intent, true_intent
           FROM battle_failures WHERE ingested=0""").fetchall()
    if not rows:
        print("no un-ingested battle failures")
        return
    n = 0
    for tid, text, served, true in rows:
        start = dataset.next_negative_index(conn, STAGE, served)
        dataset.store_negatives(conn, STAGE, served,
                                [(text, true or "other")], start_index=start)
        conn.execute("UPDATE battle_failures SET ingested=1 "
                     "WHERE traffic_id=?", (tid,))
        n += 1
    conn.commit()
    by = conn.execute(
        """SELECT intent, COUNT(*) FROM variants
           WHERE stage=? AND kind='negative' AND dropped=0
           GROUP BY 1 ORDER BY 1""", (STAGE,)).fetchall()
    print(f"✓ ingested {n} battle failures as hard negatives")
    for intent, c in by:
        print(f"  {intent:28s} {c} negatives")
    print("→ now rebuild: scripts/build_index.py && scripts/eval_slice.py")


if __name__ == "__main__":
    main()
