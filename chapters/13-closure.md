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

End state of that first campaign: serving accuracy 100%,
confident-wrong 0.00%, conversational probes green, and the
question-coverage audit running as a permanent gate beside them.

## Closure is a distribution, not a checkbox

A day later the audit taught its second lesson. It regenerates fresh
answers every run (temperature 0.9) — and a fresh sample leaked ~40%
of its answers past a corpus that had been "closed" the night before.
Closure proven on one sample is closure over that sample, nothing
more. Two consequences, both now code:

- **A judge sits inside the gate.** Some answers to a bot's question
  are *supposed* to miss: "¿tienen el king en blanco?" is a novel
  catalog question and the probe table itself demands it fall to the
  LLM lane. The old audit counted every below-threshold answer as a
  failure, which made convergence impossible. Now a boundary-aware
  judge arbitrates each unheard answer with the bot's question as
  context: coverable intent → real closure failure; novel question or
  two concerns → a correct refusal, reported but not penalized.
- **Closure became a loop, not an audit**
  (`scripts/close_question_coverage.py`): generate a fresh answer
  sample → classify → judge the unheard → ingest the coverable ones as
  positives (`register='closure'`) → rebuild, recalibrate → repeat with
  a *different persona flavor* each round (terse, chatty, formal,
  typo-ridden). Because the distribution is generative — every round is
  a sample the corpus has never seen — closure is a **rate, not a
  checkbox**. Even gate-passing leaks get ingested: the ratchet only
  tightens.

Where does the rate converge? After ~2,500 ingested-and-rebuilt
positives, fresh samples stabilize at **3.1% coverable-unheard (11 of
360 fresh answers, three independent audits)** — and the residue has a
root cause, not a backlog: semantic interleaving. "Mejor la tarjeta,
así lo divido cada mes" (an *answer*, serveable) scores 0.72 because it
lives lexically inside "¿puedo pagar con tarjeta?" (a payment-method
*question*, constitutionally blocked — the probe table demands it
miss). No threshold separates what the embedding can't. So the gate
bounds the leak rate at **5%, one in twenty**, set above the measured
asymptote — and the harm hierarchy justifies it: a coverable leak falls
*silently* to the paid lane (cents, never lies), strictly milder than
the 1.19% wrong-serves the battle campaign accepted. The surfaces that
must be exact stay exact: conversational probes 77/77 at 100%, and
confident-wrong serves at zero tolerance, everywhere, forever.

## The calibration had never learned the cluster doctrine

Why didn't the loop converge at first? The residual leaks were almost
all "No, gracias + a tiny reason" — and `declination`'s calibrated
threshold was the strictest in the system: **0.892**. Tracing which
hard negatives drove that quantile found the cause: they were
**thanks_goodbye texts** ("Todo claro, muchas gracias. Hasta luego" at
0.916). In-cluster confusions — the exact class the social-safe
doctrine declares harmless. Those negatives were seeded before the
cluster existed; they protected against nothing while strangling the
threshold that kept real declinations unheard. The predicate, the
gates and the probes had all learned the cluster; the *calibration
data* never had.

Fix at the data level, where it repairs every predicate site at once
(browser included, zero new code): the 84 in-cluster negatives are
retired (`dropped=1`, receipts kept). Recalibration: declination
0.892 → 0.693, confirmation 0.823 → 0.764 — serving accuracy still
100%, confident-wrong still zero, hit rate 12% → 49%. The real
protection — "¿Hay chance de que salga pronto el modelo de espuma?"
as a declination negative at 0.717 — still stands.

The same archaeology then found the pattern twice more.
`answer_size_posture` sat at 0.911, strangled by `want_to_buy`
negatives — texts like "busco colchón 2 plazas, duermo de costado"
that are *both* purchase intent and a size answer; serving the
size-posture template to them is correct (better, even — it advances
instead of re-asking). Retired. And the guard built for compounds
turned out to bite corpus members themselves: "el descuento me parece
lo más práctico" — an ingested positive at similarity **1.000** —
was vetoed as a price-compound. Two predicate refinements came out:

- **Corpus-exact bypass**: a verbatim match to a corpus positive is
  the strongest evidence possible; the multi/margin legs exist for
  ambiguous compounds, not for rows the corpus itself contains.
  Negative-margin stays armed — only *curated* rows bypass that.
- **Two words can't carry two concerns**: the compound guard no longer
  fires on ≤2-word fragments ("tiene garantia", "sos un bot"). The
  battle-tested compound that created the guard — "¿precio y
  garantía?" — is three words *with a conjunction*, and stays blocked.

One more receipt from the same session: the first closure campaign
ingested under a label-only judge, and re-auditing those rows with the
template-fit standard dropped 116 of 329 as serving traps ("Sí,
pasame a la gente, porfa" filed under *confirmation* would have served
a cheerful proceed-ack to someone asking for a human). The judge that
gates ingestion now is the judge that would have to approve the serve.

The user asked to "see the system grow"; growth here has a precise
meaning — **each failure class ends as an invariant the build enforces
forever.**
