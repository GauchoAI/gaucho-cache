# The dataset: generated once, curated hard

All generation ran as **batched Cerebras calls** (`gpt-oss-120b`,
concurrency 8, idempotent resume — a crashed run refills only missing
cells). Total offline cost across every round: **single-digit dollars**.

## Live counts (from `data/slice.sqlite` at build time)

| Metric | Count |
|---|---|
| Total variants generated (all rounds) | **{{stat:total_rows}}** |
| Active positives (post-curation) | {{stat:active_positives}} |
| Active hard negatives | {{stat:active_negatives}} |
| Dropped as ambiguous / compound / mislabeled | {{stat:dropped}} |
| Relabeled by arbitration | {{stat:relabeled}} |

## Generation recipe (per intent)

- **Positives**: 24 matrix cells — length (fragment → long) × register
  (formal / neutral / rioplatense slang) × noise (clean / typos) — × 4
  paraphrases ≈ 96 utterances.
- **Hard negatives**: 35 messages that *look like* the intent but
  belong elsewhere, with boundary themes targeted at observed failure
  modes (payment-method logistics, defect-vs-preference,
  restock-vs-delivery).
- **~20 human-curated boundary fragments** — the highest-value
  calibration data is hand-authorable sales intelligence: "q pasa
  falla?" seeded as a return_policy negative means a defect fragment
  can never confidently serve the returns template.

## Curation: where the accuracy actually came from

The raw generated corpus routed at 87%. Every point above that came
from corpus QA, not classifier changes:

1. **Label QA** — every variant re-judged in batched calls (58 calls,
   20 variants each). Found positives expressing the wrong intent
   ("¿Tienen garantía?" generated under brand_trust) and negatives
   mislabeled "other".
2. **Ambiguity arbitration** — cross-intent near-duplicate detection +
   leave-one-out routing disagreement, judged against boundary-aware
   definitions. Compound messages ("if it doesn't fit, can I return
   it?") and vague fragments dropped: **ambiguity is the miss path,
   never a classifier target.**
3. **Strict fragment rule** — every 1-3-word fragment arbitrated; a
   fragment that could fit two intents is ambiguous by definition.

Reproduce from scratch: `scripts/generate_variants.py` →
`scripts/clean_dataset.py` → `scripts/arbitrate_ambiguity.py` →
`scripts/seed_curated_negatives.py` → `scripts/build_index.py`.
Or pull the finished dataset: `scripts/hf_sync.py pull` (HF dataset
`miguelemosreverte/gaucho-cache`, versioned snapshots).
