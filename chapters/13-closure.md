# The Closure Principle: never ask what you can't hear

The user one-shot the demo twice in a minute. First with "Es para mi" —
a direct answer to the bot's own scripted question, met with silence.
Then with "Queria comprar un colchon, dos plazas" — the funnel's entry
intent, absent from an objection-stage slice. Both were classes, not
typos, and they generalize into one invariant:

> **A conversational cache must be CLOSED under its own questions:
> every plausible answer to every question a template asks must be
> heard — served, or refused for a structured reason. Silence after
> your own question is the one unforgivable failure.**

The invariant is checkable, so it became a gate
(`scripts/audit_question_coverage.py`): extract every template's
closing question, generate plausible customer answers, classify each
through the full stack. First run: **77 unheard answers across all 8
question-asking templates**. The audit one-shots the cache the way the
user did — systematically.

The 77 collapsed into four answer classes, each now an intent with its
own funnel-advancing template: **confirmation** ("sí, dale, avancemos"
→ proceed-or-ask), **declination** ("no, gracias" → graceful close),
**answer_size_posture** ("2 plazas, de costado" → recommendation
handoff), **answer_payment_choice** ("cuotas sin interés" → toward
close). Plus two structural lessons paid for along the way:

- **Curated rows are constitution, not data**: automated arbitration
  kept re-judging human design rulings ("Holiss", bare "sí") under
  rules written for generated noise. Curated rows are now exempt.
- **The social-safe cluster**: greet, thanks, confirmation,
  declination, answer-for-whom are mutually-safe moves — confusing two
  of them never lies to anyone. Penalizing those confusions had been
  distorting every metric and trigger; the predicate, the gates and
  the probes now share one cluster definition.

End state: serving accuracy 100%, confident-wrong 0.00%, conversational
probes green, and the question-coverage audit running as a permanent
gate beside them. The user asked to "see the system grow"; growth here
has a precise meaning — **each failure class ends as an invariant the
build enforces forever.**
