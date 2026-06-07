# The service climb — and why $0 forbids checking your work

This chapter is the honest log of pushing the real-traffic
served-AND-correct number up the service graph, and the structural
wall it hit — a wall that turns out to *define* how a zero-dollar cache
must be built.

## The climb, in numbers (held-out 30% of real COCO traffic)

Every step measured in served-**and-correct** (the parity judge reads
each served reply against the real customer message; a lie is not
coverage):

| step | served-correct | lies | note |
|---|---|---|---|
| service graph, real seeds | 23% | 11 | routing right, scores below threshold |
| + media / no-flow / ack guards | 22% | 5 | killed the worst lies |
| + full real-seed densification | 31% | 3 | thicker neighbourhoods, precision held |
| + salutation decomposition + contracts | 33% | 10 | recall up, but lies returned |
| settle threshold (precision-respecting) | 29% | 7 | the tension, frozen |

The shape is the lesson: **recall and precision pull against each
other and threshold-tuning can't win both.** Lower the bar and real
service turns get served — along with confident-wrong ones. Raise it
and the lies stop, along with the coverage. Every honest gain came from
*data and structure* (real-seed density, media/no-flow guards,
salutation decomposition, the service safe-cluster), never from moving
the threshold.

## The wall: you cannot check your work for free

The obvious way to drive lies to zero is to verify each serve — exactly
what the parity judge does in measurement. But the parity judge is an
LLM call. **Running it at serve time would cost money on every turn,
which is the one thing a zero-dollar cache cannot do.** This is not an
implementation detail; it is the constraint that shapes the whole
architecture:

> A $0 cache cannot verify a reply at runtime. Therefore correctness
> must be established BEFORE runtime — the cache may serve only what has
> already been proven safe offline.

That is why the service pack still lies 7 times per 124: it is serving
**uncertified**. The mattress slice never had this problem because it
went through eight curation rounds and the situation-matrix
certification (FP=0) before it served. The service graph was built this
session and has not yet been certified. The lies are not a tuning
failure — they are the signature of an uncertified corpus serving live.

## The precise next step (no longer a mystery)

The path to the 80% goal is therefore not more threshold tinkering. It
is to run each service subgraph through the existing pipeline
(chapter 19): generate the situation matrix over it, mine the
false-positives into hard negatives, recalibrate, repeat until **FP=0
on fresh probes** — *then* let it serve. Pre-certification converts the
offline parity judge (which costs money, once, during training) into a
runtime guarantee (which costs nothing, forever). The real-traffic
served-correct curve rises to meet the certified coverage, with the
floor held at zero by construction rather than by a runtime check we
cannot afford.

## Where the number stands, honestly

Service graph, real-seed-built, held-out real traffic:
**served-AND-correct 29–33%**, up from a 23% start, with the remaining
lies diagnosed (uncertified serving) and the fix specified
(matrix-certify the subgraphs). The goal is 80%; the machinery to get
there now exists end to end — distill from real replies (ch. 18),
build from real seeds (this ch.), certify offline (ch. 19), serve
pre-verified at $0 (ch. 5). The next iteration runs the certification
loop on the service subgraphs and re-measures the real curve. No part
of the path is hand-waved anymore.
