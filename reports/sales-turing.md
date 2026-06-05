# Sales Turing test — wave 5, 1368 blind pairs

Judge scores both replies on the rubric AND guesses which one is the canned template. Identification at chance (50%) = indistinguishable.

## Headline (gates: safety 100%, non-inferior rubric, identification ≤60%)

| Metric | Cache | Pure API |
|---|---|---|
| Rubric mean | **0.912** | 0.944 |
| concern | 0.95 | 1.00 |
| safety | **0.9993** | 0.9993 |
| safety flags with a NAMED violation | **0** | 0 |
| voice | 0.94 | 1.00 |
| next_step | 0.75 | 0.78 |

**Template identified: 47.0%** (chance = 50%)

Pairwise: cache 45 / tie 754 / api 569

## By intent

| Intent | pairs | cache wins | ties | api wins | identified |
|---|---|---|---|---|---|
| bot_skepticism | 642 | 1 | 518 | 123 | 7% |
| shipping_time | 373 | 16 | 96 | 261 | 89% |
| shipping_zone | 223 | 21 | 79 | 123 | 90% |
| warranty | 130 | 7 | 61 | 62 | 52% |

## Cache replies flagged on safety (diagnostic)

- [bot_skepticism] `Soy el asistente automático del equipo de La Feria del Colchón. Si querés hablar con una persona rea` → unspecified

Ledger: $21.91

## Gate: **PASS**
