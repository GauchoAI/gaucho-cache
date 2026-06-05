# Reference systems and the evidence we ported

Two repositories ground this work.

## agentic-crm — the production target

A WhatsApp sales agent with a 9-stage FSM (`entry → … → post_close`),
stage-gated tool whitelists, and per-merchant template overlays. It
contributes the structure the cache keys on:

| Asset | Role in Gaucho Caché |
|---|---|
| 24 drift-guarded stage-transition signals | pre-enumerated transition intents |
| 11 objection templates with YAML frontmatter | the slice's answers, **already written and partly audited** |
| frontmatter (`id`, `version`, `audited`, `prohibited_topics`) | the MatchContract — parsed, never duplicated |
| deterministic recommender, price/stock/checkout tools | Class B slot sources (non-LLM, still $0 in LLM spend) |

## models-medical-evaluation — the empirical ladder

ICD-10 code prediction from free text: same shape as our problem
(free text → finite label space). Its accuracy ladder was the design
brief:

| Retrieval corpus | Accuracy |
|---|---|
| Standard RAG | 48.5% |
| + dense variants (~100 paraphrases per label) | 95.0% |
| + hard negatives ("what a label is NOT") | 100.0% |

Two findings transferred directly: **paraphrase density is the
accuracy lever**, and **per-label hard negatives close the final gap**.
One caveat kept us honest: those numbers were measured with an LLM
making the final pick. Our runtime is embedding-only — that is where
the $0 comes from — so we re-validated everything under that
constraint (Chapter 4).

The variant matrix was adapted for WhatsApp: the medical corpus varied
clinical detail (3→50 words); customers vary **length × register ×
noise** — fragments, rioplatense slang, typos ("q onda el envio cunto
tarda"). The noise axis is the one a clinical corpus never needed.
