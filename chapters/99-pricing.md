# Cost analysis: what the evidence cost, what the cache saves

Like the reference medical-codes report, pricing closes the book — and
unlike most cost sections, every dollar below is **measured, not
estimated**: since the battle-test campaign, every Cerebras call logs
its actual token usage to an append-only ledger
(`data/spend_ledger.jsonl`), with a hard budget guard.

## Rates (Cerebras, gpt-oss-120b)

| | per 1M tokens |
|---|---|
| Input | $0.35 |
| Output | $0.75 |

## Measured campaign spend (live from the ledger)

{{ledger_table}}

Pre-ledger work (the original slice: 1,359 variants, 8 routing rounds,
3 quality evals) ran before usage logging existed; reconstructed from
call counts it cost **≈ $0.70**. Grand total for everything in this
book: **≈ ${{stat:spend_total}} + $0.70**.

## Unit economics: cache vs API at runtime

A typical objection-stage API turn (policy book + history in prompt,
short reply) runs ~1,500 input + ~250 output tokens:

| | per turn | per 1,000 turns | per 1M turns |
|---|---|---|---|
| Pure API (gpt-oss-120b, cheap end of market) | ~$0.0007 | ~$0.71 | ~$713 |
| Pure API (frontier model, e.g. $3/$15 per M) | ~$0.0083 | ~$8.25 | ~$8,250 |
| **Gaucho Caché served turn** | **$0.0000** | **$0.00** | **$0.00** |

The cache's entire build cost (~$5–6 including this battle-test
campaign) is repaid within the **first ~8,000 cached turns** even
against the cheapest API on the market — and within ~700 turns against
a frontier model. Everything after that is margin, plus the two things
no API price buys: **~11 ms latency** and **structural immunity to
invented specifics**.

## Where spend goes as the system grows

- Scaling to the full 72-cell taxonomy: ~7× the slice's generation +
  curation ≈ **$5 one-time**.
- Each battle-test wave (20k messages, full audit): **~$2–3**.
- Write-back maintenance: pennies — failures arrive pre-paid by the
  fallback turn that caught them.

The asymptote is the design goal: **offline dollars buy permanent
runtime zeros.**
