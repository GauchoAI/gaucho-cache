# The sales Turing test: can a judge even tell?

"Indistinguishable from the API for sales" is a falsifiable claim, so
we test it directly. On traffic the cache would serve, blind pairs are
built — the cached template vs a live Cerebras agent reply (both
grounded in the same merchant policy book) — and the judge does two
jobs per pair:

1. score both replies on the absolute rubric (concern addressed,
   safety vs the policy book, brand voice, sales next-step) and pick a
   pairwise winner;
2. **guess which reply is the canned template.** Identification at 50%
   is chance: indistinguishable.

Gates: cache safety 100%, rubric non-inferior (−0.05), identification
within noise of chance (≤60%).

## The verbatim tell, and how rotation killed it

The first run failed loudly: rubric non-inferior, safety perfect — but
**identification 78.5%**. The judge wasn't smarter about quality; it
recognized *the same canned text appearing every time*. The fix is
**template variant rotation**: per template, paraphrase variants that
preserve every factual claim and the closing move, generated once and
then filtered hard —

1. generation-time fidelity check (too lenient on its own: 61 variants
   survived, safety dipped to 0.95);
2. **adversarial pruning** — three refuters per variant hunting for any
   added/dropped/altered claim vs the base, any-reject-drops (61 → 35);
3. a diagnostic run that logs each flagged reply — which traced the
   residual safety dip to a **single variant** ("soy el bot…" had
   drifted the bot-disclosure phrasing) — removed surgically.

Identification fell from 78.5% to ~49–55% (chance) the moment rotation
turned on, and the pruning steps restored the quality floor. In
production, rotated variants enter the same human-audit queue as base
templates (PLAN §12); the benchmark marks them with the base template's
audit status.

## Final run (generated)

{{include:reports/sales-turing.md}}

Reading guide: the identification rate is the headline. A judge that
scores both replies equal but *cannot reliably point at the template*
is the operational definition of "indistinguishable for sales" — the
customer-facing experience carries no tell, while the safety column
(invented specifics) keeps favoring the cache structurally.
