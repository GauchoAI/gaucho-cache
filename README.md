# Gaucho Caché

**Zero-marginal-cost conversational turns for FSM-funnel chatbots.**

A semantic cache that sits in front of the LLM provider in a stage-gated
sales funnel. Because the funnel FSM makes the conversation space largely
finite (~72 stage×intent cells), the bot's answers can be pre-generated
once as a dense templated dataset and served at runtime from a local
embedding classifier — no provider call, no output tokens, $0 per turn.

## Reference repositories

| Repo | What it contributes |
|---|---|
| [`agentic-crm`](../agentic-crm) | The production target: 9-stage sales FSM (`sales-agent/src/sales_agent/stages.py`), 24 drift-guarded transition signals, 11 merchant objection templates, jinja-lite composer, disk `ResponseCache`. Design captured as [ADR-0016](../agentic-crm/docs/adr/0016-semantic-stage-cache.md). |
| [`models-medical-evaluation`](../models-medical-evaluation) | The empirical evidence: free-text → finite-label classification (ICD-10) goes 48.5% → 95% with ~100 paraphrase variants per label (`chapter_3_3_dense_variants.py`), → 100% with hard negatives. Also the methodology to port: dense-variant matrix generation, bidirectional round-trip QA, book-report evaluation harness. |

## Status

Planning. See [PLAN.md](PLAN.md) — currently under revision/iteration
before execution.
