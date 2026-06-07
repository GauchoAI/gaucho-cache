# Checkpoint: what did all of this buy?

The user asked the only question that matters at the end of a campaign:
*"What improvement have we observed thanks to the work? Are we able now
to have a zero-dollar experience or what?"* This chapter is the
accounting — measured numbers only, flattering and unflattering alike.

## Is the experience zero-dollar?

**For the modal conversation: yes, literally.** The verified purchase —
greet → "queria comprar un colchon" → size and posture → recommendation
with real products and prices → payment ladder → "en 3 cuotas" →
checkout link → thanks — runs **seven turns out of seven from cache,
$0.00**. At the start of this campaign that conversation died at
message three.

**For all traffic: no, and that is the design.** Bespoke turns fall to
the LLM at centavos. The honest metric is the cached share and what
the misses cost:

| metric | campaign start | now |
|---|---|---|
| held-out hit rate (mattress slice) | ~12% | **49%** |
| cached share, whole-funnel conversations | 13–19% (openers only) | **30–38%** incl. recommend / payments / **close** |
| fresh-paraphrase recall (hardest measure: probes never seen by corpus or calibration) | unmeasured | 37–42% slice / **69% certified** receptionist |
| the typical buying conversation | dies at turn 3 | **100% cached, $0** |

Per-conversation marginal cost: down roughly **a third on realistic
deep-funnel traffic, 100% on the typical path**.

## The result nobody ordered: it sells better

The cache was built to be cheaper without being worse. It measured
*better*:

- **Conversion doubled** — hybrid 33% / 42% / 42% vs pure-LLM 17% /
  17% / 33% on matched personas, same catalog, same seeds. The
  deterministic spine advances the funnel every single time; crispness
  converts.
- **Quality floors held everywhere**: serving accuracy 100%,
  confident-wrong 0, zero bad cached serves across hundreds of judged
  conversations, whole-conversation Turing identification at exactly
  chance (24/48).

## It generalizes

A receptionist domain — zero hand-written taxonomy, templates or
catalog — was bootstrapped from raw proxy traffic and walked the
automated pipeline to **CERTIFIED: recall 35% → 69%, FP 5 → 0,
near-misses refused 50/50**. The provider authored its own
replacement; the evidence gate decided when; the matrix said so with
numbers. For every future agent, that is the onboarding: point the
`base_url` at the proxy and let the curve climb.

## What it cost to find all of this out

**$34.19, one-time** — every dataset, every battle wave, every judge,
every simulation, every certification round, fully ledgered. The
runtime stays $0 by construction (the socket-blocked proof of chapter
5 never stopped being true). The standing trade is the one declared on
day one: **never lie to save a cent; spend cents only where templates
cannot tell the truth.**
