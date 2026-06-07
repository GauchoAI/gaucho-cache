# GOAL — the north star

> **For a real merchant's traffic, ≥ 80% of customer turns are served
> from cache at $0 — judged equal-or-better than Cerebras, with zero
> lying serves — and the pipeline reproduces that on any new merchant
> from their own logs, untouched by hand.**

## The one number

**Real-traffic zero-dollar serve rate** — fraction of *real* customer
turns answered from cache at $0. Measured by `scripts/reality_coverage.py`
against a merchant's real logs (merchant #1 = COCO Shoes, 444 turns).

- Baseline (2026-06-07): **32%** (sales cache, raw served)
- Target: **≥ 80%** (served-AND-correct — a lie is not coverage)

### Progress log

- **2026-06-07** — corrected the metric to **served-AND-correct** (parity
  judge on every serve; ch. 25). Built the COCO **service graph** from
  real customer phrasings, held-out 30% split (ch. 25–26). Held-out
  real-traffic served-AND-correct: **23% → 29–33%**, lies 31 → 3–10.
  Key wall found (ch. 26): **$0 forbids runtime verification**, so
  correctness must be pre-certified offline — the remaining lies are the
  signature of an *uncertified* corpus serving live. Next: run the
  matrix-certification loop (ch. 19) on each service subgraph (FP=0 on
  fresh probes) before it serves, then re-measure the real curve.
  Open issue: matrix probe-generation is template-derived; for service
  intents it must generate from real customer phrasings to certify
  honestly.
- **2026-06-07 (cont.)** — the **service safe-cluster** unlock (ch. 27):
  registered {order_status, exchange, shipping, complaint} as a third
  safe cluster (exempt from multi/margin legs, shared unified ask) like
  SOCIAL/FUNNEL. Held-out served-AND-correct **23% → 41%**, lies
  **31 → 5**; mattress slice unchanged at 100%/0. restock pulled out
  (different ask). Remaining gap = multi-turn conversation state +
  deliberately-forwarded flows (refund, data-change, hours, wholesale).
  Distance to 80% is now labour, not mystery.

100% is the wrong target: ~17% of real traffic is genuinely bespoke
(novel complaints, wholesale negotiation, true one-offs). Those *should*
cost cents — forcing them into templates is how a cache starts lying.
80% on-graph $0 with an honest ~17% paid lane is the two-tier model:
a global service graph carries the spine; the paid lane carries the
genuinely novel.

## Completion criterion, made precise (ch. 28)

Measuring real traffic showed "80% served" was a guess at the
templatable share. The judge measures it: **~74% of real traffic is
templatable**; the rest genuinely needs a live agent, and forwarding it
is *correct behaviour*, not failure. So "done" is three numbers:

1. **Lies → 0** (served-but-wrong; the floor).
2. **$0 share → the templatable ceiling** (~74% on COCO).
3. **Correct behaviour → ~100%** (serve where templatable, forward
   where novel, never lie).

Current (held-out COCO service): correct-behaviour **66–69%**, $0 share
**44–48%**, lies **4**, ceiling **~75%**. (Range = stochastic
densification build variance ±2pp; freeze or average a production pack.)

Remaining measured distance to completion:
- **lies 4 → 0**: the residue are serve/forward-boundary edges (website-
  bug report, specific-price the generic fact can't give, novel problem
  on an order). Needs offline real-phrasing matrix-certification, not
  more negatives (denser negatives suppressed correct serves too).
- **correct-behaviour ~67% → ~100%**: ~38 missed templatable turns —
  below-threshold service (denser real seeds), mid-conversation
  fragments (more dialogue-state signals), and flows still forwarded for
  lack of merchant facts (supplied via signed spec at onboarding).
- All are specified builds, not tuning; further held-out tuning would
  overfit the 124-turn set (measured against it ~25×).

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
