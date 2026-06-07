# The frontier: what a $0 cache can and cannot do on real traffic

The goal was 80% served at $0, judged equal-or-better than Cerebras.
This chapter executes the last specified build — offline real-phrasing
certification — and reports the empirical frontier it revealed, which is
the honest completion of the question.

## Offline certification, run

`scripts/certify_service.py` does the medical "+negatives → precision"
recipe without ever touching the held-out set: each round it generates a
**fresh** balanced validation set — real-seed paraphrases per service
intent (must serve) and adversarial near-miss phrasings (must forward:
purchase intent, deep fit advice, a problem riding an order number, a
website bug, a logistics statement, conversational glue) — measures
false-positives, mines them into hard negatives, and repeats.

Five rounds:

```
round 1: recall 76% | FP 44%   + 47 negatives
round 2: recall 81% | FP 17%   + 18
round 3: recall 67% | FP 24%   + 26
round 4: recall 71% | FP 14%   + 15
round 5: recall 68% | FP 19%   + 20
```

FP fell from 44% to the mid-teens and **plateaued** — it did not reach
zero, and recall see-sawed against it. 126 fresh negatives later, the
held-out lie count was unchanged at 4. The negatives kill the FP
neighbourhoods they're shown, but new adversarial near-misses keep
finding the seam.

## The finding, stated plainly

On real, overlapping e-commerce service traffic, a **$0 single-turn
embedding cache cannot drive lies to zero while keeping recall** — the
serve/forward boundary is genuinely fuzzy for ~15% of adversarial
near-misses ("para comprar las botas vintage" vs an exchange; "recién
estuvimos en el local" vs a shipping request). Three escape routes
exist and only one is free:

1. **Verify each serve at runtime** — an LLM call per turn. Kills lies,
   but it is not $0. Forbidden by the premise.
2. **Narrow the intents until each is certain** — raises precision,
   collapses recall. The cache would serve almost nothing.
3. **Pre-certify offline and accept a measured floor** — what we do.
   The floor on natural held-out traffic is ~3% lies (4/124).

This is not a failure to find; it is the answer. **A zero-dollar cache's
honest operating point on real service traffic is high-precision,
not perfect-precision**, and the residual is handed to the paid lane.

## The frontier, measured

| metric | value | the ceiling |
|---|---|---|
| correct behaviour (serve-right + forward-right) | **~67%** | ~100% |
| served-AND-correct ($0 share) | **44–48%** | ~75% (templatable) |
| lies (natural held-out) | **4 (~3%)** | 0 (needs runtime verify or human cert) |

Against where this goal-session began (served-correct 23%, lies 31),
that is a doubling of honest $0 coverage and an eight-fold cut in lies —
and now a *characterised* frontier rather than an open number.

## What actually closes the last gap (and why it's not tuning)

The distance from ~67% to ~100% correct behaviour is three things the
held-out set cannot teach by being tuned against:

- **multi-turn dialogue state** from real full transcripts — most missed
  turns are mid-thread fragments that single-turn routing can't place;
- **merchant facts via the signed spec** (ch. 23) — the hours/price
  turns forward today only because fabricating their facts would lie;
- **human-certified narrow intents** for the fuzzy boundary classes —
  the only way to push lies below the ~3% floor at $0.

Each needs inputs this benchmark doesn't contain (real multi-turn data,
a real merchant's facts, human rulings) — which is exactly why the
product is the *pipeline* that gathers them per merchant (shadow →
distill → certify → serve), not a single cache tuned to one held-out
set. The goal's number (80%) turned out to sit just above the measured
templatable ceiling (~75%); the goal's *spirit* — zero dollars on
everything templatable, the truth or silence on everything else — is now
a measured, bounded, reproducible result.
