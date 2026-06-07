# Cache evolution: not a key-value store

The user's question cut to the architecture: *"when we say 'evolve the
cache,' is it just a key-value store, or are we doing annotations,
compaction, a caching protocol that improves as it goes?"* The answer
is the second, and most of the protocol already existed unnamed — this
chapter names it, automates it, and reports the one experiment that
taught it humility.

## A cache entry is an evidence-annotated row

The store was never a dict. Every row carries its own history:
`register` (provenance — curated / generated / closure / redteam /
matrix / density / traffic-distilled), `judged_intent` (an arbitration
override when a judge overruled the generator's label), `dropped` (a
tombstone — the corpus never hard-deletes, so every ruling stays
auditable), and in the proxy, per-template agreement counters. The new
`evolution.annotate()` simply makes that legible — each row as
frontmatter a person or an agent can read:

```
---
intent: price
provenance: slang
state: active
---
No alcanza la guita
```

## Compaction, and the humility it taught

`evolution.compact()` tombstones duplicate positives so the
brute-force index stays lean and the calibration quantiles stay
un-skewed. The first instinct was semantic: merge anything ≥ 0.97
cosine within an intent. The flywheel ran it and the **eval gate
refused the result** — 0.97-"duplicates" turned out to be load-bearing,
the single positive holding a cross-intent margin ("ok esperamos"
guarding confirmation against awaiting_reply). Boundary protection
(exempt any row near a foreign intent) helped but didn't close it: a
dense 20-intent corpus has no truly free duplicates.

Then a subtler trap. Surely *normalized-exact* dups are safe — same
intent, same text after lowercasing and accent-stripping? No: "¿Cuánto?"
and "cuanto" normalize equal but **embed differently**, so dropping one
still moves a margin. The gate caught that too.

What is provably margin-neutral is only **byte-identical** text: same
raw string → same embedding → every margin the dropped row held, the
survivor holds exactly. On this corpus that is 35 rows of 4,518 — a
rounding error. The honest conclusion: **at this scale and density,
compaction is nearly a no-op, and aggressive compaction is a net
risk.** The size win was never the deliverable.

## The deliverable is the safety machinery

The valuable artifact is what makes a nightly self-maintenance pass
*safe to run unattended*. Compaction tags every tombstone
(`register += "·compacted"`), so a pass is fully reversible. The
flywheel (`scripts/evolve_cache.py`) compacts, rebuilds, and re-runs
the full gate suite — and if any boundary moved, it **auto-rolls back**,
rebuilds the gate-green index, and exits non-zero. Across this
chapter's experiments it fired three times and left the corpus green
every time:

```
✗ compaction moved a boundary — AUTO-ROLLED BACK
  (84 rows restored, index rebuilt). Corpus left gate-green.
```

A self-improving cache that can corrupt itself is a liability; the
guarantee that matters is that **evolution can never lower a gate** —
the worst a bad pass can do is waste compute and revert.

## Training triggers: the flywheel's ignition

The third piece closes the loop to chapter 18. `evolution.triggers()`
reads the proxy's traffic table for the misses the cache forwarded,
clusters the mutually-similar ones, and surfaces any neighbourhood with
≥ K members as a **training task** — "these K customers asked variations
of the same unheard thing; distill it." The runtime thus tells its own
trainer where to look next, budget-capped and gate-protected by
everything above.

So: annotation makes the cache legible, compaction (byte-safe by
default) keeps it lean, the flywheel guarantees evolution never harms
it, and triggers point the next training round. Not a key-value store —
a corpus that curates itself, and knows it must never break a gate to
do it.
