# Reality check: we were benchmarking the wrong domain

The user stopped me with the most important correction in this book:
*"I gave you a real dataset from a friend who has an e-commerce. Did
you notice the patterns are maybe not the ones we'd expect to be easy?
Sometimes a conversation just starts with 'what is the status of this
item?' What you're lacking is a red team that finds real consumer
behaviour."* He was right, and the proof is a single number.

## 32%

Every chapter before this measured the cache against traffic the cache's
own machinery generated — synthetic personas walking the funnel we
designed. So I ran the cache against **444 real customer turns** from 59
real WhatsApp conversations (COCO Shoes), stateful per conversation,
and labelled every turn by what the customer actually wanted:

| what real customers do | share of traffic | served at $0 |
|---|---|---|
| exchange / return | 18% | 11% |
| order status | 16% | 29% |
| shipping coordination | 14% | 17% |
| thanks / greeting | 21% | ~88% |
| complaint / restock / product Q | 19% | ~11% |
| **purchase** | **2%** | 27% |

**The cache serves 32% of real traffic at $0 — and the entire sales
funnel this book obsessed over is 2% of what real customers do.** The
social spine I built is excellent (greeting 95%, thanks 81%); the
*business* — exchanges, order status, shipping, complaints — is a set
of subgraphs the funnel never modelled. The "no answers for my words"
the user kept hitting wasn't a tuning problem. It was a *domain* problem:
I had mapped the 2%.

## The formal artifact, finally

This is the thing the user said he couldn't see — the graph and to what
degree it's explored — and it is now a permanent measurement
(`scripts/reality_coverage.py`, report at `reports/reality_coverage.json`):
real traffic, decomposed by topic, with each uncovered subgraph named
and ranked by how often real customers hit it. Not fresh-paraphrase
recall against our own generator — coverage against reality. It is the
red team he asked for: not invented attacks, real behaviour, scored
against the cache.

## The two-tier answer, and who authors it

The uncovered subgraphs (exchange, order-status, shipping, restock,
complaint) are not bespoke per merchant — they are the **global
e-commerce service graph** every shoe shop, every store, shares. That is
the user's two-tier model: a global service base beneath each client's
custom sales funnel. And the templates need not be hand-written — the
store already authored them, in its own replies. Pointing the chapter-18
distiller at the COCO transcripts (`scripts/ingest_coco.py` →
`distill_traffic.py`) mines exactly that:

> provide_reference_number → *"¡Genial `<name>`! Con el número de pedido
> `<order_id>` lo revisamos y te confirmamos `<status>`. Si todo está
> listo, lo enviamos `<eta>`…"*
> ask_for_updates → *"¿Podés indicarme a qué pedido o producto te
> referís?"*

These are **templated flows with slots**, not verbatim answers — the
distiller had to be upgraded from "copy a reusable reply" to
"synthesize one clean slotted template from the cluster's real replies,"
because real service replies are saturated with per-customer specifics.
The slots (`<order_id>`, `<eta>`, `<status>`) are the class-B lookup of
chapter 16, now over an order database instead of a catalog. The store
wrote the flow; the cache learns it; a backend fills the blanks; the
turn costs $0.

## What this re-frames

The zero-dollar goal does not change — it sharpens. "Zero dollars" is
not a property of a clever matcher; it is a property of a **closed graph
over real behaviour**. The honest path to it is: measure real traffic
(32% today), name the uncovered subgraphs by real frequency, distill
their flows from the merchant's own replies, certify them with the
situation matrix, and watch the real-traffic $0 curve climb — the
number that was always the point, now measured against the customers who
actually write in. The funnel was the easy 2%. The next chapters earn
the rest.
