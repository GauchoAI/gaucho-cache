"""Cache evolution: the cache is not a key-value store.

A cache entry is an EVIDENCE-ANNOTATED row, and the store already carries
the annotations — `register` (provenance: who put it here), `judged_intent`
(arbitration override), `dropped` (tombstone, never a hard delete),
plus per-template agreement counters in the proxy. This module names and
automates the passes that keep that living corpus healthy:

  compact()   merge near-duplicate positives (cosine ≥ DUP_T, same intent),
              summing provenance; tombstone the absorbed rows. Pure local,
              no LLM. Shrinks the brute-force index and de-skews the
              calibration quantiles without losing a single distinct
              meaning. The serving gates MUST be re-run after (caller).
  annotate()  emit each row's self-knowledge as readable frontmatter —
              provenance, audit state, neighbours — so any external tool
              (or agent) can inspect what the cache knows and why.
  triggers()  read the proxy traffic: K mutually-similar MISSES in a
              neighbourhood → a training task for that neighbourhood. The
              flywheel's ignition, budget-capped and gate-protected.

Nothing here invents serving behaviour; it curates the substrate the
predicate runs on.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
DB = REPO / "data" / "slice.sqlite"
DUP_T = 0.97           # near-duplicate cosine for merge
TRIGGER_K = 4          # this many similar misses → a training task
TRIGGER_T = 0.82       # misses within this cosine form a neighbourhood


@dataclass
class CompactionReport:
    before: int
    merged: int
    after: int
    by_intent: dict[str, int]


COMPACT_TAG = "·compacted"   # appended to register so a pass is reversible


def _norm(t: str) -> str:
    import re
    import unicodedata as ud
    return re.sub(r"[^a-z0-9ñ ]+", "", ud.normalize("NFKD", t.lower())).strip()


def compact(db: Path = DB, stage: str = "objection",
            dup_t: float | None = None) -> CompactionReport:
    """Tombstone duplicate active positives within each intent. Absorbed
    rows are tagged (register += COMPACT_TAG) so a pass is fully reversible.

    Default (dup_t=None): EXACT-text dedup — same intent, identical
    normalized text. This is provably margin-neutral (a kept identical
    row holds every margin the dropped one did) and is the only
    compaction this densely-interleaved corpus tolerates; the experiment
    that taught us so is chapter 22.

    Aggressive (dup_t set, e.g. 0.97): semantic near-dup merge with
    boundary protection. Use only behind the flywheel's gate+rollback —
    on a dense corpus it WILL move boundaries, and the flywheel is built
    to catch and undo that."""
    from collections import defaultdict
    con = sqlite3.connect(db)
    rows = con.execute(
        "SELECT id, intent, text, register FROM variants WHERE stage=? AND "
        "kind='positive' AND dropped=0 ORDER BY id", (stage,)).fetchall()
    before = len(rows)
    if before < 2:
        return CompactionReport(before, 0, before, {})

    merged_ids: set[int] = set()
    by_intent: dict[str, int] = {}

    if dup_t is None:
        # BYTE-exact dedup: same intent, identical RAW text → identical
        # embedding → provably margin-neutral. (Normalized-equal but
        # raw-different rows — "¿Cuánto?" vs "cuanto" — embed differently
        # and CAN move a margin; chapter 22 learned this the hard way, so
        # the safe default is strict byte equality.)
        seen: dict[tuple[str, str], int] = {}
        for rid, intent, text, reg in rows:
            key = (intent, text)
            if key in seen and reg != "curated":
                merged_ids.add(rid)
                by_intent[intent] = by_intent.get(intent, 0) + 1
            else:
                seen.setdefault(key, rid)
    else:
        from .classifier import Embedder
        vecs = Embedder().encode([r[2] for r in rows])
        intents = np.array([r[1] for r in rows])
        sims = vecs @ vecs.T
        np.fill_diagonal(sims, -1.0)
        foreign = np.array([
            float(sims[i][intents != intents[i]].max())
            if (intents != intents[i]).any() else -1.0 for i in range(before)])
        load_bearing = foreign >= 0.80
        idx_by_intent: dict[str, list[int]] = defaultdict(list)
        for i, r in enumerate(rows):
            idx_by_intent[r[1]].append(i)
        for intent, idxs in idx_by_intent.items():
            kept: list[int] = []
            for i in idxs:
                if rows[i][3] == "curated" or load_bearing[i]:
                    kept.append(i); continue
                if any(float(vecs[i] @ vecs[k]) >= dup_t for k in kept):
                    merged_ids.add(rows[i][0])
                    by_intent[intent] = by_intent.get(intent, 0) + 1
                else:
                    kept.append(i)

    if merged_ids:
        con.executemany(
            "UPDATE variants SET dropped=1, register=register||? WHERE id=?",
            [(COMPACT_TAG, i) for i in merged_ids])
        con.commit()
    con.close()
    return CompactionReport(before, len(merged_ids), before - len(merged_ids),
                            by_intent)


def rollback_compaction(db: Path = DB) -> int:
    """Undo the last compact() — restore every tagged tombstone."""
    con = sqlite3.connect(db)
    cur = con.execute(
        "UPDATE variants SET dropped=0, register=replace(register,?,'') "
        "WHERE register LIKE '%'||?||'%' AND dropped=1",
        (COMPACT_TAG, COMPACT_TAG))
    n = cur.rowcount
    con.commit()
    con.close()
    return n


def annotate(db: Path = DB, stage: str = "objection",
             intent: str | None = None, limit: int = 20) -> list[str]:
    """Each row's self-knowledge as frontmatter — the cache made legible."""
    con = sqlite3.connect(db)
    q = ("SELECT intent, register, judged_intent, dropped, text FROM variants "
         "WHERE stage=? AND kind='positive'")
    args: list = [stage]
    if intent:
        q += " AND intent=?"
        args.append(intent)
    q += " ORDER BY dropped, id LIMIT ?"
    args.append(limit)
    out = []
    for it, reg, judged, dropped, text in con.execute(q, args):
        fm = [f"intent: {it}", f"provenance: {reg or 'unknown'}",
              f"state: {'tombstoned' if dropped else 'active'}"]
        if judged and judged != it:
            fm.append(f"arbitrated_from: {it} → {judged}")
        out.append("---\n" + "\n".join(fm) + f"\n---\n{text}\n")
    con.close()
    return out


def triggers(traffic_db: Path | None = None, domain: str = "objection",
             k: int = TRIGGER_K, t: float = TRIGGER_T) -> list[dict]:
    """Mine the proxy traffic for miss neighbourhoods worth training.

    Returns [{size, exemplar, members}] — each a cluster of ≥k mutually
    similar misses. The flywheel reads this and enqueues a distill round
    for that neighbourhood (budget-capped by the caller)."""
    traffic_db = traffic_db or REPO / "data" / "proxy_traffic.sqlite"
    if not traffic_db.exists():
        return []
    from .classifier import Embedder
    con = sqlite3.connect(traffic_db)
    try:
        misses = [r[0] for r in con.execute(
            "SELECT user_msg FROM traffic WHERE domain=? AND served_by="
            "'provider'", (domain,)).fetchall()]
    except sqlite3.OperationalError:
        return []
    con.close()
    if len(misses) < k:
        return []
    vecs = Embedder().encode(misses)
    used = set()
    clusters = []
    for i in range(len(misses)):
        if i in used:
            continue
        members = [j for j in range(len(misses))
                   if j not in used and float(vecs[i] @ vecs[j]) >= t]
        if len(members) >= k:
            used.update(members)
            clusters.append({"size": len(members), "exemplar": misses[i],
                             "members": [misses[j] for j in members[:6]]})
    return sorted(clusters, key=lambda c: -c["size"])
