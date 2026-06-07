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

REUSE_SYS = ("You synthesize ONE reusable, templated reply for a cluster of "
             "customer messages, learning the FLOW and TONE from how a live "
             "store actually answered. Output ONLY the reply text itself "
             "(one message, may use <slot> placeholders), or exactly SKIP if "
             "the cluster is too incoherent to answer with one templated flow.")
REUSE_PROMPT = """Customers send messages like:
{examples}

The live store answered messages in this cluster with replies like:
{reply}

Write ONE clean reply that could serve EVERY message in this cluster.
Match the store's warm WhatsApp tone, but:
- replace anything customer-specific with an <slot> placeholder —
  <name>, <order_id>, <eta>, <status>, <size>, <tracking> — and list the
  slots (angle brackets, never curly braces). (Slots are filled later by a backend lookup; you
  are authoring the FLOW, not a concrete answer.)
- if the cluster's right move is to ASK for a missing detail (e.g. "pasame
  el numero de pedido"), that question IS the reusable reply, no slots.
- reusable=false ONLY if the cluster is too incoherent to answer with one
  templated flow."""


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
        # several real replies as STYLE/FLOW evidence — the template is
        # synthesized clean with slots, not copied from the noisiest one
        sample = "\n".join(f'- "{replies[i][:160]}"' for i in cluster[:5])
        body = (await client.chat(
            REUSE_SYS, REUSE_PROMPT.format(examples=ex, reply=sample),
            temperature=0.2, max_tokens=300)).strip().strip('"')
        if not body or body.upper().startswith("SKIP") or len(body) < 8:
            return None
        return intent, cluster, body

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
