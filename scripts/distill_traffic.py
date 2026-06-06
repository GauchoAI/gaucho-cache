#!/usr/bin/env python3
"""Distill a domain pack from raw proxy traffic — no hand-written taxonomy.

Input: the proxy's traffic log (user turns + the provider's own replies).
Output: data/domains/<domain>/ — index.npz + thresholds.json +
variants.json — loadable by the LearningProxy. The provider is the
unwitting author of its own replacement:

  1. embed all logged user turns; greedy-cluster (cosine >= CLUSTER_T)
  2. clusters with support >= MIN_SUPPORT become intent candidates;
     a judge names each and rejects heterogeneous ones
  3. per cluster, the most central provider reply becomes the template
     candidate; a judge audits it for REUSABILITY (no names, dates,
     order numbers — must fit every message in the cluster verbatim)
     and may return a cleaned generalization
  4. thresholds calibrate against cross-cluster similarity (an intent
     must score above what OTHER clusters' members reach against it)

Usage: CEREBRAS_API_KEY=... uv run python scripts/distill_traffic.py --domain recepcion
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from gaucho_cache import spend
from gaucho_cache.cerebras import BatchClient
from gaucho_cache.classifier import Embedder, StageIndex, strip_salutation

CLUSTER_T = 0.74
MIN_SUPPORT = 4
THRESHOLD_DELTA = 0.02

NAME_SYS = ("You curate intents for a WhatsApp assistant. Output ONLY JSON "
            '{"intent": "<snake_case>", "coherent": true|false, '
            '"meaning": "<one line>"}.')
NAME_PROMPT = """These customer messages were clustered together:
{examples}

If they all express ONE intent, name it (snake_case, specific). If the
cluster mixes intents, coherent=false."""

REUSE_SYS = ("You audit a reply for verbatim reusability. Output ONLY JSON "
             '{"reusable": true|false, "cleaned": "<the reply, generalized '
             'if needed>", "why": "..."}.')
REUSE_PROMPT = """Customers send messages like:
{examples}

The live agent once answered one of them:
"{reply}"

Could this exact reply (or a lightly generalized version of it) be sent
VERBATIM to every message above, every time, without ever being wrong?
Reject if it contains specifics that vary per customer (names, dates,
order numbers, one-time amounts). If a small edit makes it reusable
(dropping a name, neutralizing a date), return that as "cleaned"."""


def greedy_clusters(vecs: np.ndarray, texts: list[str]) -> list[list[int]]:
    clusters: list[list[int]] = []
    cents: list[np.ndarray] = []
    for i in range(len(texts)):
        best, bj = -1.0, -1
        for j, c in enumerate(cents):
            s = float(vecs[i] @ c)
            if s > best:
                best, bj = s, j
        if best >= CLUSTER_T:
            clusters[bj].append(i)
            m = vecs[clusters[bj]].mean(axis=0)
            cents[bj] = m / np.linalg.norm(m)
        else:
            clusters.append([i])
            cents.append(vecs[i])
    return clusters


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", required=True)
    ap.add_argument("--db", type=Path,
                    default=REPO / "data" / "proxy_traffic.sqlite")
    a = ap.parse_args()

    con = sqlite3.connect(a.db)
    rows = con.execute(
        "SELECT user_msg, provider_reply FROM traffic WHERE domain=? AND "
        "provider_reply IS NOT NULL", (a.domain,)).fetchall()
    if len(rows) < MIN_SUPPORT:
        sys.exit(f"only {len(rows)} logged turns — keep shadowing")
    texts = [strip_salutation(r[0]) or r[0] for r in rows]
    replies = [r[1] for r in rows]
    print(f"{len(rows)} logged turns in domain '{a.domain}'")

    emb = Embedder()
    uv = emb.encode(texts)
    clusters = [c for c in greedy_clusters(uv, texts) if len(c) >= MIN_SUPPORT]
    print(f"{len(clusters)} clusters with support ≥ {MIN_SUPPORT}")

    client = BatchClient("distill_traffic")

    prev_pack = REPO / "data" / "domains" / a.domain / "variants.json"
    prev_names = (sorted(json.loads(prev_pack.read_text()))
                  if prev_pack.exists() else [])

    async def curate(cluster: list[int]):
        ex = "\n".join(f"- {texts[i]}" for i in cluster[:10])
        hint = (f"\nIf one of these existing intent names fits, REUSE it "
                f"verbatim: {', '.join(prev_names)}." if prev_names else "")
        v = await client.chat_json(NAME_SYS,
                                   NAME_PROMPT.format(examples=ex) + hint,
                                   temperature=0.0)
        if not (isinstance(v, dict) and v.get("coherent")):
            return None
        intent = str(v.get("intent", "")).strip()
        # most central provider reply = canonical answer candidate
        rvecs = emb.encode([replies[i] for i in cluster])
        sims = rvecs @ rvecs.T
        central = cluster[int(np.argmax(sims.mean(axis=1)))]
        rj = await client.chat_json(
            REUSE_SYS, REUSE_PROMPT.format(examples=ex, reply=replies[central]),
            temperature=0.0)
        if not (isinstance(rj, dict) and rj.get("reusable")):
            return None
        return intent, cluster, str(rj.get("cleaned") or replies[central])

    curated = [c for c in await asyncio.gather(*(curate(c) for c in clusters))
               if c]
    if not curated:
        sys.exit("no reusable intents found yet — keep shadowing")

    # ---- build the pack ------------------------------------------------------
    out = REPO / "data" / "domains" / a.domain
    out.mkdir(parents=True, exist_ok=True)
    intents, vecs = [], []
    variants: dict[str, list[str]] = {}
    for intent, cluster, body in curated:
        variants[intent] = [body]
        for i in cluster:
            intents.append(intent)
            vecs.append(uv[i])
    V = np.vstack(vecs)
    idx = StageIndex(V, np.array(intents), np.array(["positive"] * len(intents)),
                     np.array([""] * len(intents)))
    idx.save(out / "index.npz")

    # thresholds: an intent must score above what other clusters reach into it
    thresholds = {}
    for intent in set(intents):
        m = np.array([i == intent for i in intents])
        if (~m).any():
            cross = float((V[~m] @ V[m].T).max())
        else:
            cross = 0.6
        thresholds[intent] = {"threshold": min(0.88, cross + THRESHOLD_DELTA),
                              "margin": 0.05, "negative_margin": 0.03}
    (out / "thresholds.json").write_text(json.dumps(thresholds, indent=1))
    (out / "variants.json").write_text(
        json.dumps(variants, ensure_ascii=False, indent=1))
    print(f"✓ domain pack → {out} ({len(variants)} intents: "
          f"{', '.join(sorted(variants))}) | ledger ${spend.spent():.2f}")


if __name__ == "__main__":
    asyncio.run(main())
