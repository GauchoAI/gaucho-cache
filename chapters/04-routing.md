# Routing: eight rounds to zero confident-wrong

The gate was fixed before the first run and never moved: **≥95%
held-out routing accuracy AND confident-wrong = 0**. A slice that
misses often but never lies passes; a slice that hits 99% with one
confident wrong answer fails.

## The evolution

| Round | Change | Routing | Confident-wrong |
|---|---|---|---|
| 1 | raw generated corpus | 87.0% | 6 (3.0%) |
| 2 | full label QA + q95 calibration | 87.6% | 5 (2.6%) |
| 3 | dedup + LOO arbitration | 93.2% | 4 |
| 4 | E1: mpnet-base-v2 (adversarial 4→1) | 92.6% | 4 (all fragments) |
| 5 | strict fragment rule | 94.1% | 1 |
| 6 | payment-boundary sweep | 95.7% | 1 |
| 7–8 | boundary negatives ×35 + curated fragments | **95.7%** | **0** |

Every confident-wrong fixed between rounds 1 and 8 was a **corpus
defect** — a mislabel, a cross-intent duplicate, a compound message, or
a thin negative pool on a boundary. The classifier itself changed once
(round 4, embedding model swap).

## The compound hit predicate

Score alone never serves. A hit requires all of:

```
score        >= intent_threshold        (calibrated on own negatives)
top1 - top2  >= margin                  (no ambiguity between intents)
top1 - nearest_negative >= neg_margin   (not a known imposter pattern)
match-contract preconditions pass       (stage, state, audit)
```

## Final evaluation report (generated)

{{include:reports/slice-eval.md}}
