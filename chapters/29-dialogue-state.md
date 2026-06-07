# Dialogue state and fact flows: the lie-free recall levers

With the goal redefined honestly (ch. 28: lies→0, $0-share→the ~75%
templatable ceiling, correct-behaviour→~100%), this chapter executes
the lie-free levers that close the recall debt — and shows which gains
are real and which would have been fabrication.

## Fact flows by regex, not embedding

Two missed subgraphs were store-hours and payment-info. The first
instinct — add them as embedding intents — *lowered* served-correct
(42→37%): thin synthetic seeds for low-frequency intents polluted the
routing of the real ones. The fix is to respect their nature: hours and
payment questions are **lexically distinctive** ("horario", "abren",
"a qué precio", "efectivo", "cuotas"), so they're served by a precise
regex (`service.detect_fact_intent`) over the merchant facts, never by
embedding routing. Distinctive-lexical → regex; everything else →
embedding. That recovered the turns without polluting the index:
served-correct 42→46%.

Crucially, these flows exist **only when the merchant supplied the
fact**. Templating "our hours are…" without real hours would fabricate
— the exact lie the project forbids. `data/cocoshoes_facts.json` is a
mock (the catalog/orders pattern); a real deploy supplies it via the
signed spec (ch. 23). No facts, no flow, the turn forwards — correctly.

## Dialogue state, content-typed

Chapter 27 tried multi-turn continuation with a word-count proxy ("any
short turn while a flow is active continues it") and it added lies — so
it was reverted. The correct version is **content-typed**: a fragment
continues the active flow only if it carries that flow's relevant
content — a size for exchange ("talle 38"), a date for shipping
("el jueves"), "novedad" for order-status — and doesn't route
confidently elsewhere (`service.continues_flow`). Precise instead of
coarse, it recovered the mid-conversation fragments at the cost of a
single lie, where the word-count version cost four.

## Two precision guards

The honest 2×2 surfaced the remaining lies one by one. Two were clean:
"Para comprar las botas vintage" is purchase intent, not an exchange
("para comprar" → forward); "Ahí le pasé el número" says the customer
already sent it, so re-asking is wrong ("ya/ahí pasé" → forward). Both
folded into the no-flow guard. Lies 6→4 with no loss of correct serves.

## Where the climb stands

Held-out real COCO service traffic:

| metric | session start | now |
|---|---|---|
| served-AND-correct ($0 share) | 23% | **48%** |
| correct behaviour (serve-right + forward-right) | — | **69%** |
| lies (floor → 0) | 31 | **4** |
| $0 ceiling (templatable share) | — | **76%** |

served-AND-correct more than doubled; lies fell eight-fold; the cache
now does the right thing on 69% of real turns and is closing on the 76%
ceiling. Every gain was lie-respecting: regex for distinctive facts,
content-typed (not word-count) dialogue state, merchant-fact-gated
flows that forward rather than fabricate. The remaining 4 lies are
genuine serve/forward-boundary edges (a website-bug report, a
specific-price ask the generic fact can't satisfy, a novel problem
riding an order number) — the residue that only offline real-phrasing
certification (ch. 19's pipeline, pointed at service intents) drives to
zero. That, plus denser real-seed coverage for the still-below-threshold
serves, is the last measured distance to the goal.
