# Gaucho Caché

**Zero-marginal-cost conversational turns for FSM-funnel chatbots —
proven, not promised.**

A semantic cache that sits in front of the LLM in a stage-gated sales
funnel. The FSM makes the conversation space finite (stage × intent
cells); a **local embedding model** routes each customer message into
that space in ~10 ms, serves a pre-audited template on a confident
match, and falls back to the LLM only on genuine novelty.

## The four proofs (P0.5 slice: objection stage, 10 intents)

| Claim | Gate | Result |
|---|---|---|
| Perfect routing | ≥95% held-out accuracy, confident-wrong = 0 | **PASS** — 95.7%, 0.00% |
| $0 at runtime | full path with networking socket-blocked | **PASS** — 184 turns, 0 attempts, p50 11 ms |
| Quality = pure API | blind-judged, safety 100% + non-inferior rubric | **PASS** — 0.972 = 0.972; safety **1.00 vs 0.91** |
| Product-agnostic | zero product literals in cached values | **PASS** — 10/10 pure sales moves |

Full methodology and results: **[the book report](index.html)**
(`scripts/build_book.py`, chapter mechanism ported from
[models-medical-evaluation](https://miguelemosreverte.github.io/models-medical-evaluation/)).

## Demo (3 commands, standalone)

```bash
git clone git@github.com:GauchoAI/gaucho-cache.git && cd gaucho-cache
uv sync
uv run gaucho-cache tour        # scripted showcase (8 vignettes)
```

`uv run gaucho-cache demo` opens the interactive REPL — type customer
messages in Spanish (typos and slang welcome) and watch the decision
pipeline live. First run downloads the embedding model (~1 GB, one
time); after that the runtime is fully offline.

One-shot classification:

```bash
uv run gaucho-cache classify --stage objection "la garantia q onda?"
# {"decision":"hit","intent":"warranty","score":0.97,...,"serve_eligible":true}
```

## Reproducibility

- **Code**: this repo. The dataset (`data/slice.sqlite`), embedding
  index, and calibrated thresholds are committed — a fresh clone demos
  with zero setup beyond `uv sync`.
- **Dataset on the HF Hub** (house policy): versioned snapshots at
  [`miguelemosreverte/gaucho-cache`](https://huggingface.co/datasets/miguelemosreverte/gaucho-cache)
  — `scripts/hf_sync.py {push|pull|status}`, labels tied to git SHAs.
- **Regenerate from scratch** (~$2 on Cerebras, batched):
  `generate_variants.py → clean_dataset.py → arbitrate_ambiguity.py →
  seed_curated_negatives.py → build_index.py → eval_slice.py`.
  Every step is idempotent and resumable.
- **Re-run the proofs**: `eval_slice.py` (routing),
  `prove_zero_spend.py` (no key needed), `eval_quality.py`
  (CEREBRAS_API_KEY), `check_product_agnostic.py`.

## Repo map

```
gaucho_cache/        library: classifier, contracts, dataset, demo, CLI
scripts/             pipeline + proof harnesses + hf_sync + build_book
data/                slice.sqlite, intent taxonomy, contract extensions
index/               embedding index + calibrated thresholds
examples/laferia/    vendored merchant templates (the cache's answers)
chapters/            book-report sources  →  index.html
reports/             generated proof reports (markdown)
PLAN.md              the design dialogue (Claude ↔ Codex, §§1–14)
```

## References

- `../agentic-crm` — production target: 9-stage FSM, stage-gated tools,
  merchant template overlays ([ADR-0016](../agentic-crm/docs/adr/0016-semantic-stage-cache.md)).
- `models-medical-evaluation` — the dense-variant + hard-negative
  evidence (48.5% → 95% → 100%) and the strict-expectations evaluation
  style this project inherits.
