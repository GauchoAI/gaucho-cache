# Gaucho Caché — The Plan

> Draft for iteration. Nothing here is frozen; revise freely.

## 1. Mission

Serve the overwhelming majority of customer turns in an FSM-funnel
chatbot at **$0 marginal LLM cost** and **millisecond latency**, by
replacing the per-turn provider call with:

```
inbound message
   │
   ▼
local embedding (~10ms, CPU)          ← sentence-transformers MiniLM-class
   │
   ▼
nearest-neighbour vs per-stage utterance index   ← ~100 variants/intent
   │
   ├── score ≥ per-intent threshold ──► template render (jinja-lite)
   │                                       │
   │                                       ├── Class A: static text → reply
   │                                       └── Class B: + deterministic slot
   │                                           lookup (price/stock/order/
   │                                           checkout-link) → reply
   │
   └── score < threshold ──► LLM fallback (Class C)
                                │
                                └── write-back: new template candidate +
                                    utterance variant (human-gated)
```

The FSM is what makes this possible: 9 stages × enumerated intents is a
**finite label space** (~72 cells), and classifying into a finite label
space from free text is a solved problem *if the retrieval corpus is
dense enough* — that is the finding we are porting from
`models-medical-evaluation`.

## 2. What each reference repo proves / provides

### agentic-crm (production target)

| Asset | Path | Role here |
|---|---|---|
| 9-stage FSM + tool gating | `sales-agent/src/sales_agent/stages.py` | Stage = first cache-key component; gating already bounds what each stage can answer |
| 24 transition signals (drift-guarded) | `STAGE_TRANSITION_SIGNALS` in same file | 24 intents, pre-enumerated, guaranteed in sync with FSM |
| 11 objection templates | `merchants/laferia/templates/objections/*.md` | 11 intents whose *answers already exist as templates* |
| Per-stage prompt decoration | `merchants/laferia/templates/stages/*.md.j2` | Transition-intent answers (stage openers) already exist |
| Jinja-lite composer | `agentkit/src/agentkit/prompt/composer.py` | Template render layer — reuse as-is |
| Disk response cache w/ volatile masking | `agentkit/src/agentkit/llm/response_cache.py` | Layer-1 exact cache; the semantic cache slots in beside it |
| Gym (simulated customer + evaluator) | `gym/` | Free source of realistic test traffic + LLM-judge for QA gates |
| Design ADR | `docs/adr/0016-semantic-stage-cache.md` | Taxonomy v1 + cacheability classes (summarised in §4) |

### models-medical-evaluation (empirical evidence + methodology)

| Finding / asset | Path | What we port |
|---|---|---|
| Dense variants lift accuracy 48.5% → 95% | `chapter_3_3_dense_variants.py` (10 detail levels × 10 paraphrases per label) | The generator pattern: per-intent variant matrix |
| Hard negatives lift 95% → 100% (35/35) | chapter 3.4 (report) | Per-intent negative sets → per-intent thresholds |
| Round-trip consistency QA | chapter 3 (code→description→code) | Template → classify-back → must land on own intent |
| Idempotent, resumable generation loop | `get_missing_variants()` / `INSERT OR REPLACE` | Same resume pattern, SQLite-backed |
| Book-report harness | `generate_book_report.py`, `dataset_generation.py` | Publish our accuracy/cost results the same way |

**⚠ Critical caveat (keeps us honest):** the medical repo's retrieval is
LLM-in-the-loop — `chapter_3_3_rag_test.py` stuffs the top examples into
a prompt and lets Claude pick the final code. Its 95%/100% were measured
*with an LLM judge at the end*. Gaucho Caché's runtime is
**embedding-only** (that's where the $0 comes from), so those numbers
are an upper bound until we re-measure. Experiment E2 (§6) exists
precisely to close this gap. Our problem is also easier in two ways
(~72 labels vs 46,237; conversational stage prior narrows candidates to
~10–15 intents) and harder in one (WhatsApp Spanish: typos, slang,
voseo, fragments).

## 3. Architecture

Three components, mirroring the agentic-crm coupling axes:

1. **`gaucho_cache` library (merchant-agnostic, English).**
   - `Classifier`: embeds inbound text, per-stage NN search, per-intent
     thresholds. Brute-force numpy cosine (~8.6k vectors → no vector DB).
   - `TemplateStore`: (stage, intent) → template + slot schema +
     cacheability class.
   - `CacheDecision`: hit (template + slots to resolve) | miss (reason).
   - Audit events for every decision (hit/miss/score/intent) — same
     spirit as the FSM stage-audit trail.
2. **Dataset pipeline (offline, one-time + write-back increments).**
   - Generator: taxonomy → variant matrix + hard negatives via Cerebras
     (`gpt-oss-120b`), idempotent/resumable, SQLite-backed.
   - QA gates: round-trip consistency, near-duplicate pruning,
     threshold calibration from negatives.
   - Embedding index builder: variants → normalized vectors → `.npz`
     artifact, versioned.
3. **Integration shim (agentic-crm side, later phase).**
   - A pre-LLM hook in `SalesOrchestrator`: consult `CacheDecision`
     before dispatching to the provider; on hit, skip the LM loop and
     emit the rendered reply through the normal `respond_to_user` path
     so persistence/audit stay identical.
   - Shadow mode first (§6 E4): decide-but-don't-serve, log agreement.

### Cache key

```
(stage, intent, slot_signature)
```

- `stage` — free, the orchestrator already knows it.
- `intent` — classifier output.
- `slot_signature` — the *names* of slots the template needs (not
  values); values resolve at render time from deterministic sources.
  Keying on names keeps the index small and the hit rate high.

### Variant matrix (adapted from the medical 10×10)

The medical detail axis (3→50 words) doesn't fit WhatsApp. Our axes:

| Axis | Levels | Examples |
|---|---|---|
| Length / completeness | 4 (fragment → full sentence) | "precio?" → "che me decís cuánto sale el colchón ese?" |
| Register | 3 (formal / neutral / rioplatense slang) | "¿Cuál es el precio?" / "cuánto sale" / "cuánta guita es" |
| Noise | 2 (clean / typos+abbreviations) | "q onda el envio cunto tarda" |

4 × 3 × 2 = 24 cells × ~4 paraphrases ≈ **~100 variants per intent**,
matching the density that produced the 95% result. Noise injection is
the axis the medical corpus never needed — WhatsApp demands it.

## 4. Intent taxonomy v1 (summary — full table in ADR-0016)

| Group | Count | Answer source already exists? |
|---|---|---|
| Global (greet, thanks, ask-human, bot-skepticism, what-do-you-sell, off-topic, abuse) | 7 | persona overlay + objection template |
| Transition intents (`STAGE_TRANSITION_SIGNALS`) | 24 | per-stage `.md.j2` openers |
| Stage-hold intents | ~30 | partial (policy snippets, product cards) |
| Objection categories | 11 | **yes — verbatim templates** |
| **Total cells** | **~72** | |

Cacheability classes:

- **A — static template.** Zero external calls.
- **B — template + deterministic slot** (WooCommerce price/stock,
  `get_order`, checkout-link mint, recommender output). Zero **LLM**
  dollars; non-zero latency.
- **C — LLM fallback.** Compositional/novel. Target residual: <15% of
  turns at launch, shrinking via write-back.

Known-hard cell: `needs`-stage free-prose slot-filling (profile
capture). Enumerable attributes go regex/local-NER; prose stays Class C
in v1. Do not over-promise here.

## 5. Phases

| Phase | Deliverable | Gate to advance |
|---|---|---|
| **P0 — Taxonomy freeze** | Taxonomy v1 reviewed; per-intent template sources mapped; slot schemas written | Human sign-off (this iteration loop) |
| **P1 — Dataset generation** | SQLite of ~72 intents × ~100 variants + ~20 negatives, Spanish rioplatense, via Cerebras; idempotent generator | Spot-check 10% of cells; near-dup rate <10% |
| **P2 — Index + classifier** | Embedding index artifact + `Classifier` with per-intent thresholds calibrated on negatives | **E1** + **E2** pass (§6) |
| **P3 — Template completion** | Templates for all A/B cells (reuse objection + stage openers; write the missing ~30 hold-intent templates) | Round-trip QA: 100% of templates classify back to own intent (**E3**) |
| **P4 — Shadow mode** | Integration shim in agentic-crm, decide-but-don't-serve; gym traffic + (if available) replayed real conversations | **E4**: ≥85% hit-rate proposal w/ ≥98% intent agreement vs LLM behaviour on hits |
| **P5 — Serve Class A** | Static cells served live; B/C still LLM | 1 week shadow-parity in audit events; objection CSAT unchanged |
| **P6 — Serve Class B + write-back loop** | Deterministic-slot cells live; miss→template-candidate pipeline w/ human review queue | Residual LLM rate <15%; zero wrong-template incidents |

Each phase produces a chapter in a book-report (port of
`generate_book_report.py`) so results are published the same way the
medical evaluation was.

## 6. Experiments (the science between phases)

- **E1 — Embedding model bake-off.** Candidates: multilingual MiniLM,
  `paraphrase-multilingual-mpnet`, BGE-m3 (small), a Spanish-tuned
  model. Metric: intent accuracy on held-out variants (train/test split
  *within* each intent's variant set). Pick smallest model within 1pt of
  best.
- **E2 — Embedding-only vs LLM-in-the-loop.** Reproduce the medical
  repo's comparison on *our* corpus: (a) embedding NN top-1, (b)
  embedding top-5 → Cerebras picks (cheap hybrid), (c) full LLM
  classify. Quantifies exactly what the $0 constraint costs in accuracy.
  If (a) lags badly, (b) is the documented fallback architecture —
  ~50 input tokens per turn instead of $0, still ~100× cheaper than
  full generation.
- **E3 — Round-trip QA.** Every template → classifier → own intent.
  Ambiguous templates get rewritten, not threshold-hacked.
- **E4 — Shadow agreement.** On gym + replayed traffic: would-have-hit
  rate, intent agreement vs what the live LLM actually did (stage
  transitions taken, tools called), per-stage breakdown.
- **E5 — Adversarial probe.** Gym customer-agent prompted to be
  ambiguous/compositional/code-switching; measures false-positive rate
  at calibrated thresholds. Hard gate: confident-wrong-answer rate ~0
  (a miss costs cents; a wrong answer costs trust).

## 7. Cost model

| Item | Estimate |
|---|---|
| Dataset generation (~8.6k short gens, Cerebras) | low single-digit $ |
| Template authoring for ~30 hold cells (LLM-drafted, human-reviewed) | <$1 + review time |
| Embedding index build (local) | $0 |
| Runtime, Class A/B turns | **$0 LLM** |
| Runtime, Class C residual (~15% → shrinking) | existing per-turn cost × residual rate |
| Re-validation per merchant/catalog change | re-run affected cells only (idempotent generator) |

## 8. Risks

| Risk | Mitigation |
|---|---|
| Confident wrong template (worst failure) | Per-intent thresholds from hard negatives; E5 gate; serve A before B; audit every hit |
| Embedding-only accuracy below medical-repo numbers | E2 quantifies; hybrid top-5+Cerebras fallback documented |
| Spanish/voseo/typos degrade off-the-shelf embeddings | Noise axis in variant matrix; E1 includes Spanish-tuned models |
| Staleness (catalog/policy changes) | Class B resolves slots live; template content versioned with overlay; cache key includes template version |
| Multi-turn context dependence | Key includes slot *names* only; stage carries the conversational prior; anything needing deeper history is Class C by design |
| Write-back pollutes the corpus | Human review queue before activation; round-trip QA on every candidate |

## 9. Open questions (for this iteration loop)

1. Where does the classifier live — inside the sales-agent process, or
   a sidecar service the orchestrator calls? (In-process is simpler;
   sidecar lets backend + gym reuse it.)
2. Should write-back candidates flow through the existing Testing
   Studio review UI instead of a new queue?
3. Per-merchant indexes from day one, or laferia-only until P6?
4. Do we cache `respond_to_user` text only, or also the interactive
   sends (`send_buttons`/`send_list` payloads are templatable too)?
5. Is the 85% hit-rate gate for P4 the right bar, or should we gate on
   cost-reduction % instead?
6. Naming: `gaucho_cache` python package vs folding into `agentkit` as
   `agentkit.semcache` once proven?
