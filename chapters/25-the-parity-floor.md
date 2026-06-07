# Climbing toward the goal — and the floor that wouldn't let me cheat

With GOAL.md set (≥80% real-traffic $0, served equal-or-better than
Cerebras), I started the climb on the real COCO service traffic. This
chapter is the honest log of the first ascent — including the moment the
system refused to let me fake it.

## The build

Step 1 was the service graph, seeded the only honest way: **real
customer phrasings as the training set.** `build_service_domain.py`
takes the 444 labelled real turns, holds out 30% of conversations for
testing, and builds an index from the train turns grouped by intent —
order_status, exchange_return, shipping_coordination, restock,
complaint, greeting, thanks. The templates are the audited service
flows (`gaucho_cache/service.py`), class-B over a mock order DB seeded
with real order numbers harvested from the transcripts.

Three levers, applied in order, each measured on the held-out 30%:

1. **Real seeds, raw** → 31% served.
2. **Densification** (paraphrase each real seed, the medical 48.5%→95%
   move) → 39%.
3. **The service safe-cluster + stateful walk** — order_status,
   exchange, shipping, complaint all answer a no-reference opener
   identically ("pasame tu número de pedido"), so a mis-route among them
   is harmless; and a bot that just asked for the number reads the next
   "#33421" in context (the conversation graph, not isolated turns) →
   **44% served.**

## The floor caught me

44% looked like progress. Then I added the parity floor the GOAL
demands — a judge reading every served reply against the customer's
actual message: *is this reply correct, or did the cache just emit
something?* The verdict was brutal and essential:

> **served 55/124 (44%) — but served-AND-CORRECT only 24/124 (19%).
> 31 of the 55 serves were WRONG.**

My coverage levers had been manufacturing lies: lowered thresholds and
"serve any short turn while a reference is pending" served confident
nonsense to turns that didn't fit. The raw 44% was a number I could
have reported; the floor made sure I couldn't. **A lie is not coverage.**
That is the whole thesis of this project, now enforced against real
traffic: the metric is not "served," it is "served *and correct*," and
the gap between them is the count of times the cache would have lied.

## Tightening to honesty

So the real work began — not maximizing serves, but maximizing
*correct* serves while driving wrong serves to zero:

- the stateful continuation now fires only on an actual order number or
  a clear affirmation ("sí", "ese mismo"), never any short turn;
- in-cluster acceptance only when the predicate truly clears its legs,
  not on an ambiguous margin.

Result on the held-out 30%:

| metric | raw serves | served-AND-correct | lies |
|---|---|---|---|
| coverage-maximised | 44% | 19% | 31 |
| **honesty-tightened** | 31% | **23%** | **11** |

Precision rose (lies 31→11, correct 24→28) — the right direction — and
**served-and-correct is now the headline number `reality_coverage.py`
reports, measured against the 80% goal.** The honest baseline for the
service graph is 23%, with 11 floor breaches still to eliminate.

## What this chapter banks

The number went *down* (44→31 raw) and that is the chapter's point: the
project would rather report 23% true than 44% with a third of it
fabricated. The path to 80% is now unambiguous and un-gameable — every
gain must survive the parity judge. The next breadcrumbs: kill the 11
remaining lies (precision to 100%), then lift correct serves with
richer flows and denser real-seed coverage, subgraph by subgraph, the
curve measured in served-*and-correct* every step. The floor is not an
obstacle to the goal; it is the goal's definition.
