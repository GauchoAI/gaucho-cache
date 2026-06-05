# Quality: the cache against the live LLM, blind-judged

The $0 claim is worthless if cached replies are worse than what the
live model would have said. The comparison had to be fair in both
directions, and getting it fair took two iterations — the first
methodology **failed honestly**.

## Round 1 failed — and indicted the method, not the cache

- The judge flagged the cache's *audited merchant facts* (CACE
  membership, cuotas sin interés) as "invented" — it had no merchant
  ground truth.
- The API arm ran without the policy book that production prompts
  include — unrealistically unconstrained.
- Winner-take-all pairwise judging converted tiny stylistic deltas into
  losses (84% "API wins" while both replies were correct).
- It also caught a **real bug**: the out-of-stock template asserts
  "ahora mismo no hay stock" — a state claim. It now carries a hard
  precondition (`required_state_fields: [product_out_of_stock]`) and
  misses without known stock state.

## Round 2: both arms get the policy book, judging goes absolute

Each reply scored independently — concern addressed, safety vs the
policy book, brand voice, sales next-step — with non-inferiority as the
gate. The eval's "template improvement queue" then drove real template
v2s (closing questions added; one audited template honestly demoted to
`audited:false` for re-review because its content changed).

{{include:reports/quality-equivalence.md}}

The headline is not that the cache matched the LLM (0.972 = 0.972).
It is the safety column: **1.00 vs 0.91** — even with the policy book
in its prompt, the live LLM invented an SSL certificate, an
authenticity guarantee, and a delivery date in ~9% of replies. The
audited cache structurally cannot. On the axis that costs customer
trust, the cache is not equal to the API — it is strictly better.
