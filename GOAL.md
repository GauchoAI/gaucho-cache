# GOAL — the north star

> **For a real merchant's traffic, ≥ 80% of customer turns are served
> from cache at $0 — judged equal-or-better than Cerebras, with zero
> lying serves — and the pipeline reproduces that on any new merchant
> from their own logs, untouched by hand.**

## The one number

**Real-traffic zero-dollar serve rate** — fraction of *real* customer
turns answered from cache at $0. Measured by `scripts/reality_coverage.py`
against a merchant's real logs (merchant #1 = COCO Shoes, 444 turns).

- Baseline (2026-06-07): **32%**
- Target: **≥ 80%**

100% is the wrong target: ~17% of real traffic is genuinely bespoke
(novel complaints, wholesale negotiation, true one-offs). Those *should*
cost cents — forcing them into templates is how a cache starts lying.
80% on-graph $0 with an honest ~17% paid lane is the two-tier model:
a global service graph carries the spine; the paid lane carries the
genuinely novel.

## The floors (must hold at every step or the gain doesn't count)

1. **Parity** — served turns judged ≥ Cerebras (in-context judge).
2. **No lying** — 0 confident-wrong, 0 contradicting serves; covered-
   surface breaches unrepresentable by construction (ch. 21).
3. **Certified** — each subgraph clears the situation matrix (FP=0,
   ch. 19) before it serves live.
4. **$0 runtime, ledgered** — the socket-blocked guarantee (ch. 5).

## The path (each step measured against REAL traffic)

| step | subgraph | real share | cum. $0 target |
|---|---|---|---|
| 0 | spine (greet/thanks) — done | 21% | 32% |
| 1 | order_status | +16% | ~46% |
| 2 | exchange / return | +18% | ~62% |
| 3 | shipping coordination | +14% | ~74% |
| 4 | restock + product question | +11% | ~83% |
| — | complaint / wholesale | 17% | stays paid, by design |

Each step: distill the flow from the merchant's own replies → mock the
backend lookup (order DB) for its slots → certify via the matrix →
re-measure the real curve. **Done = the curve crosses 80% with all four
floors green.**

## The claim that makes it a product

The last clause is the real test: **the pipeline gets a NEW merchant
there from their logs alone** — shadow → distill → certify → serve, no
hand-tuning. COCO is merchant #1; every step is built merchant-agnostic
so merchant #2 runs the same path. Lead decision (2026-06-07): target
80%, pipeline-general from day one.
