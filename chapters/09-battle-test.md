# Battle test: independent traffic at scale

Held-out variants share the training corpus's generator distribution —
they understate reality. The battle test attacks the cache with traffic
from an **independent simulator**: sampled personas (region × age ×
mood × typing style) expressing concerns that include, at realistic
rates, what the cache must refuse — payment-method questions, off-topic
requests, and **compound messages** carrying two concerns at once.

Every served decision that disagrees with ground truth is LLM-audited
before it counts: the generator mislabels too (more than half of
apparent errors were the generator's fault, not the cache's).

## The wave loop: write-back convergence on fresh traffic

Each wave is freshly generated (new seed, never seen); between waves,
confirmed failures are ingested as hard negatives and thresholds
recalibrate. Error on *fresh* traffic falls monotonically:

| Wave | Traffic | Confirmed wrong serves | Novelty false-serve |
|---|---|---|---|
| 1 (raw cache) | 11,978 | 79 / 1,505 (**5.25%**) | 1.76% |
| 2 | 19,897 | 44 / 1,634 (2.69%) | 0.41% |
| 3 | 29,940 | 43 / 2,577 (1.67%) | 0.27% |
| 4 | 19,897 | 21 / 1,677 (1.25%) | 0.23% |
| 5 | 19,898 | **17 / 1,426 (1.19%, CI 0.75–1.90%)** | **0.14%** |
| 6 (after the conversational layer: 13 intents) | 9,918 | **14 / 1,227 (1.14%)** | **0.04%** |

The held-out variant gate stayed PASS (95.7% / 0 confident-wrong)
through every recalibration. The ~1.2% asymptote on independent traffic
is dominated by borderline compounds and judge noise — and the same
write-back loop keeps running in production, where every miss is also a
fallback turn that already paid for its own audit.

> Honest framing: 0.00% on held-out variants is what the *designed*
> distribution allows; ~1.2% confirmed-wrong at a 7–9% serve rate on
> *independent* traffic is the deployable number, with novelty
> false-serves at 0.14%.

Wave 1's dominant failure was structural: compounds served a single
template ("cuánto tarda la entrega **y** cómo es la devolución?" →
shipping_time). Two fixes, both now permanent parts of the system:

1. **Multi-intent predicate leg** — if the second-best distinct intent
   also clears its own threshold, the message is treated as compound
   and misses.
2. **Failure write-back** — every judge-confirmed wrong serve is
   ingested as a hard negative of the intent that lied
   (`scripts/ingest_battle_failures.py`). The negative-margin leg then
   blocks that pattern's whole neighbourhood. This is the battle-test
   version of the medical repo's "teach what a label is NOT".

One calibration lesson surfaced on the way: battle negatives are
near-positives by construction, and letting them into the global
threshold quantile collapsed serve rate (12.4% → 3.5%). They now act
only through the targeted negative-margin leg; thresholds calibrate on
the designed negatives.

## Final wave-2 report (generated)

{{include:reports/battle-test.md}}
