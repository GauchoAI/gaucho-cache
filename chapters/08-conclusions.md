# Conclusions and the road to the full funnel

## The four proofs

| Claim | Gate | Result |
|---|---|---|
| Perfect routing | ≥95% accuracy, confident-wrong = 0 | **PASS** — 95.7%, 0.00% |
| $0 at runtime | socket-blocked execution, 0 attempts | **PASS** — 184 turns, p50 ~11 ms |
| Quality = pure API | safety 100% AND non-inferior rubric | **PASS** — 0.972 = 0.972; safety 1.00 vs 0.91 |
| Product-agnostic | zero product literals | **PASS** — 10/10 pure sales moves |

## What we learned

1. **Corpus quality is the whole game.** Eight rounds, one classifier
   change. Every confident-wrong was a corpus defect: a mislabel, a
   cross-intent duplicate, a compound message, a thin negative pool.
   The medical repo's 48.5→95→100 ladder was corpus work; so was ours.
2. **Ambiguity is the miss path.** Fragments and compound messages get
   dropped from the classifier's targets, not threshold-hacked into
   them. At runtime they fall through to the LLM — which is exactly
   where they belong.
3. **Hard negatives are authorable sales intelligence.** The most
   valuable calibration data — boundary fragments like "q pasa
   falla?" — can be written by hand in minutes per boundary.
4. **The safety asymmetry is structural.** A generative model with the
   policy in its prompt still invents specifics ~9% of the time. An
   audited template cannot. For commerce, that asymmetry may matter
   more than the cost savings.

## Next

- Human re-audit of the v2 templates (restores serve-eligible coverage).
- Hit-rate tuning on shadow traffic (P4 of the plan) — current
  thresholds are deliberately conservative.
- Scale the recipe from 10 intents to the full **72-cell taxonomy**
  (global intents, 24 transition intents, ~30 stage-hold intents) —
  same generation + curation pipeline, same gates.
- Write-back loop: every LLM fallback proposes a new template candidate
  through the existing merchant review workflow.

---

*Reproduce everything*: code on GitHub (`GauchoAI/gaucho-cache`),
dataset + index on the HF Hub (`miguelemosreverte/gaucho-cache`,
versioned snapshots), demo: `uv run gaucho-cache tour`.
