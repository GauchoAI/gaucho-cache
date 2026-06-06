# The transfer proof: "any conversation" means any domain

The battle-tested mattress cache correctly refuses another store's
questions — so the unbounded claim ("perfect any conversation") rests on
one thing: does the engine transfer? Chapter 7 promised the cached
values are sales moves, not product data. We cashed that promise against
the real dataset itself.

From **58 real COCO Shoes conversations** (444 customer messages), with
zero engine changes: 198 messages bucketed into 5 intents by
deterministic vocabulary mining (no LLM), 5 templates written mirroring
the real agents' own moves (ask the order number, ask the size, ask the
postal code), one embedding pass — a working shoes cache in minutes,
for $0.00 of generation.

| Real openers (59, leave-one-out) | Mattress cache | **Shoes cache** |
|---|---|---|
| Served | 22 (social + order ask) | **25 — incl. 8 order-status, 3 size-change** |
| Fallback | 37 (out of domain — correct) | 34 (long product-specific tails) |

This is the floor, not the ceiling: defaults thresholds, no variants, no
negatives, no calibration. The mattress slice started at 87% routing and
reached a 1.1% audited error floor through the (now fully scripted)
pipeline — ~$1 of batched generation would put the shoes cache on the
same ladder.

The unbounded claim, restated precisely: **any conversation, in any
domain, is either served indistinguishably ($0, ~5ms, judges at chance)
or handled by Cerebras itself — and every fallback is a pre-paid
training example that moves the boundary.** The recipe is the product.
