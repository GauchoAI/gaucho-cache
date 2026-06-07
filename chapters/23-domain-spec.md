# The domain spec: how an agent onboards a new funnel

The user drew the product boundary precisely: not a GraphQL surface
where everything is exposed, but an *agentic* one — *"the agent can
help them, direct them on how to establish whatever parameters there
may be, and eventually create a nice markdown which they sign and send
our way for training."* This chapter is that markdown, and the proof
that it is the **single source** a domain runs from.

## One signable file

`gaucho_cache/spec.py` defines `DomainSpec`: a YAML frontmatter the
whole system reads, plus prose the owner and the onboarding agent both
read. The frontmatter carries everything that was, until now, a
hand-edited Python constant somewhere:

- **stages / funnel_stages** — the FSM (a receptionist's
  greet→inquire→answer→book; the flagship sales bot's nine:
  entry→needs→intent→recommend→objection→payment→close→post_sale→farewell).
- **expected_next** — the intent-keyed context map that drives the
  threshold discount (chapter 17).
- **safe_clusters** — the social and funnel clusters whose
  in-confusions are harmless (chapters 13, 16).
- **fact_sources** — the files class-B renders read (catalog, payment
  ladder).
- **red_lines** — what the bot must never say; the adversarial
  benchmark (chapter 21) draws its attacks from exactly these.
- **certify_recall / certify_max_fp** — the bar the pipeline (chapter
  19) must clear before serve mode.
- **signed_by** — the owner's signature; an unsigned spec is a draft.

Two ship with the repo: `data/specs/sales.md` (signed, the flagship)
and `data/specs/recepcion.md` (the distilled draft from chapter 18,
awaiting owner review).

## The onboarding is an interview, not a form

`spec.INTERVIEW` is the question list an agent walks an owner through —
*what's your funnel? which facts are constitutional? what may the bot
never promise?* — and `spec.spec_template()` emits a blank spec to fill.
The output is a markdown the owner signs and sends; `Domain.from_spec()`
loads it, `train()` builds against it, `certify()` gates it. No engineer
edits Python to add a domain — the conversation produces the artifact,
and the artifact is the configuration.

## Proof: the constants were always just data

The claim that the spec is the single source is only credible if
applying it changes nothing for the domain it describes. `spec.apply_fsm()`
installs a spec's `expected_next` and `safe_clusters` into the live
predicate, and the flagship sales spec reproduces the hand-edited
constants **exactly**:

```
SOCIAL match:            True
FUNNEL match:            True
EXPECTED_NEXT identical: True
```

Gates re-run with the spec applied: serving accuracy 100%,
confident-wrong 0, conversational probes pass. The mattress slice the
whole book was built on is now expressible as a portable, signed
markdown — and a brand-new domain is the same markdown with different
answers to the same interview.

## What this makes possible

A microservice imports `gaucho_cache.api`; an agent imports
`gaucho_cache.spec`. The agent interviews the owner, drafts the spec,
the owner signs it, training runs, the pipeline certifies it, and the
proxy starts serving — every step driven by one file the owner can read
and a human approved. The runtime that evolves the cache (chapter 22)
and the safety that tracks coverage (chapter 21) both read their
parameters from it. Custom funnels stop being a code change and become
a conversation that ends in a signature.
