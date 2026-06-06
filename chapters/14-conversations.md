# End-to-end: Cerebras plays the customer

Single-message waves cannot find conversation-state holes — the user
proved it thrice ("Es para mi", "de costado", each an answer the bot's
own previous turn invited). Their directive: simulate whole
conversations, with Cerebras playing customers from a persona matrix —
the agentic-crm gym's method, ported to the cache.

`scripts/simulate_conversations.py`: personas (mood × typing style ×
goal, from buying a 2-plaza mattress to chasing an order) hold
multi-turn WhatsApp conversations against the FULL hybrid: cache serves
where the predicate allows; Cerebras-as-fallback answers the rest, so
dialogue flows as production would. A judge then audits **every cached
reply in its conversational context**, and failures persist for
write-back.

## Results (two independent waves)

- Wave 1 (seed 11): 60 conversations, 362 turns — **0 bad cached
  replies in context, 0 conversations flagged**; 19% of turns cached.
- Wave 2 (seed 12): cached turns 48 (13%) | LLM turns 319 | bad cache replies (judged in context): 0 | convs flagged: 0 | ledger $23.45

The zero matters more than the coverage: in living dialogue, when the
cache speaks, it is never wrong — and when unsure, it hands to the LLM
mid-conversation without the customer noticing the seam. Coverage grows
exactly as this book documents: every miss is a logged, pre-paid
training example.

Three mechanisms were forged by this chapter's failures: the
**curated-exact lane** (a verbatim match to a human-curated row cannot
be vetoed by similarity noise), **partial-answer coverage** ("de
costado" alone answers half a two-part question and must be heard), and
**bare-ack canonicalization** ("dale"/"ok" belong to confirmation,
nowhere else).
