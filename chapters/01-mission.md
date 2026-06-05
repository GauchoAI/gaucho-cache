# Mission: zero-dollar conversational turns

A sales chatbot built on a **finite state machine** does not face an
unbounded conversation space. Nine stages, enumerated transitions, a
fixed objection taxonomy — the FSM turns "anything a customer might
say" into a **finite label space** of stage × intent cells.

Gaucho Caché exploits that: classify each inbound WhatsApp message with
a **local embedding model** (CPU, ~10 ms), serve a pre-audited template
on a confident match, and fall back to the LLM only on genuine novelty.

```
inbound message
   → local embedding (~10ms, CPU, $0)
   → nearest-neighbour vs per-stage variant index
   → compound predicate: score AND margin AND negative-margin
     AND match-contract preconditions AND audited
   → HIT: render template ($0)   |   MISS: LLM fallback (costs cents)
```

The optimization order is fixed and non-negotiable:

> confident_wrong_rate ≈ 0, then hit rate, then latency/cost.
> A miss costs cents. A wrong cached answer costs trust.

This book documents the proof-of-concept slice: **one stage
(objection), 10 intents**, evaluated to four hard gates — perfect
routing, zero runtime spend, quality parity with the live LLM, and
product-agnostic cache values.
