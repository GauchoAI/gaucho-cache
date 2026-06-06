# The conversation Turing test: the whole sale, blind

The goal that drove the last three chapters was stated by the user in
one sentence: *"perfect any conversation until it really feels as if
we are talking to cerebras directly."* Chapter 10 tested that claim at
the level of single replies — a judge caught the verbatim template
78.5% of the time until variant rotation killed the tell. But a
conversation is where caches are supposed to die: the seams between
cached turns and live turns, the rhythm changes, the moment a template
almost-but-not-quite answers. So the final experiment judges **entire
sales conversations**.

## Protocol

Matched pairs from the gym machinery (`scripts/turing_conversations.py`):
the same persona, mood, style, goal, bed size and sleeping posture —
one conversation served by the **hybrid** (class-A templates, class-B
catalog renders, LLM lane for the rest), its twin served by **pure
LLM**, lane markers stripped. Two blind judgments:

- **Identification** (n=48, each conversation alone): the judge knows
  one of the two stores uses cached/templated replies, and must say
  whether *this* conversation is the cached one — plus the tell that
  gave it away. Gate: accuracy within the 95% binomial bound of chance
  (≤ 62.5% at n=48).
- **Preference** (n=24 matched pairs, order randomized): which
  salesman did better — warmth, concreteness, funnel progress, would
  you buy? Gate: hybrid ≥ 45% (non-inferiority).

One anti-tell was added before the run, paying forward chapter 10's
lesson: the class-B renders rotate among deterministic phrasings,
seeded per conversation ("Estas son mis recomendaciones…" / "Mirá, para
una cama queen yo iría por alguno de estos…" / "Te separé lo mejor que
tengo en…"). Rotation, never generation — still zero tokens.

## Results

| metric | result | gate |
|---|---|---|
| identification accuracy | **24/48 = 50%** | ≤ 62.5% — **exactly chance** |
| hybrid preferred | **11/24 = 46%** | ≥ 45% — non-inferior |

The identification transcript is the satisfying part. When judges
guessed "cached" and happened to be right, their stated tells were
*"pre-formatted product table, fixed discount options, ready-made
checkout link"* — but they cited the **same tells when wrong**, because
the pure-LLM salesman also formats product lists, also tabulates
cuotas, also pastes checkout links. The structure that screams
"template" is just what good WhatsApp selling looks like. With phrasing
rotation covering the seams, there is nothing left to detect: the
discriminator's accuracy is a coin flip.

Preference reasons split on the same axes in both directions — "mayor
calidez, información concreta, avanzó más en el funnel" appears in
hybrid wins and control wins alike. The judges are choosing between
two competent salesmen, not between a robot and a human.

## The closing argument

Read the last four chapters as one experiment:

- The cache's replies, judged in context across hundreds of simulated
  conversations: **zero bad serves** (ch. 14, 15, 16).
- The cache's effect on the only business number: conversion **more
  than doubled** against pure LLM on matched personas (ch. 16).
- The cache's detectability at whole-conversation level: **chance**
  (this chapter).

Which yields the thesis in its final form: a conversation where the
spine — greet, qualify, recommend, price, close — is served for $0
from audited templates and a product catalog, and the meat is rented
from a live LLM only when the customer is genuinely bespoke, is
**indistinguishable from, converts better than, and costs a fraction
of** the same conversation fully generated. It does not merely feel
like talking to Cerebras directly. Blind, at the level of the whole
sale, it cannot be told apart — and it sells more mattresses.
