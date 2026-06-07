# The situation matrix: the medical benchmark, ported whole

The user closed the loop back to where this project started: *"do we
have a benchmark that says — consider this conversation, this
situation, CACHED. Now hit it with paraphrases, a short and long
matrix of them, and see if the cache still holds; and then false
positives and negatives — like we do for the medical book?"*

models-medical-evaluation's central discipline was exactly that: per
cached situation, a dense paraphrase matrix (densification took recall
48.5% → 95%) and hard negatives (→ 100% precision). Our eval gate
inherited the *spirit* — but it grades against held-out rows from the
corpus's own generator. `scripts/benchmark_matrix.py` ports the
benchmark whole, with one upgrade that makes it strictly harsher:
**every probe is fresh** — generated at benchmark time, never seen by
the corpus, the calibration, or any judge. Nothing grades its own
homework.

## Protocol

Per cached situation (an audited intent and its template):

- **True probes** — length {short fragment, one sentence, 2–3 sentences
  with harmless context} × register {casual voseo, formal usted,
  typos/abbreviations} — the WhatsApp axes, K per cell. Each must HIT
  (in-cluster serves count, per the social/funnel doctrine: a for-whom
  probe served the want-to-buy question is the same funnel move).
- **Near-misses** — messages that share the situation's vocabulary but
  mean something else, so serving the template would be wrong. Each
  serve of *this* intent on one of these is a **false positive. Gate:
  zero** — the medical bar.

And because it loads any domain pack, the same script is the
**certification step for distilled domains**: a traffic-mined pack
(chapter 18) must pass the matrix before broad serve mode.

## First measurement — the 48.5% moment

The mature mattress slice, fresh probes: **recall 30%, 3 false
positives.** Sobering and correct — the held-out eval had flattered us
(its probes come from the same generator as the corpus). The three FPs
were real serving traps ("me llegó el pedido pero faltan 2 artículos"
got the generic order-status template — which ignores the actual
problem). The medical response, in the medical order:

1. the 3 FPs → hard negatives (the ratchet);
2. density for the dead rows (out-of-stock, awaiting, payment-choice,
   declination — 144 fresh positives by construction);
3. one boundary row the eval gate caught in *my own density batch* —
   dropped (the gates police their authors too).

Second measurement: **recall 42%, FP 1, near-misses refused 135/136.**
The long-message row doubled. The matrix also localizes what remains:
the residual weakness is one confusable triangle — restock vs shipping
vs order-status — and the payment-choice/Mercado-Pago interleaving the
closure chapter already priced. Fresh-paraphrase recall is the honest
number, and it is lower than any number this book reported before,
*because it is the hardest number this book has measured*. The serving
floor stands unchanged: misses cost cents and never lie.

## Certifying the distilled pack

The receptionist pack — mined from traffic eight hours before this
chapter — went through the same matrix:

- Run 1: recall 41%, **9 false positives — certification FAIL.** The
  pack, born without negatives, over-served gloriously: the dental
  free-consultation template answered *"¿la primera consulta para mi
  coche es sin costo? estoy pensando cambiar de mecánico"*. A cache
  with no negatives doesn't know what it doesn't know.
- `--ingest-fp`: each run's false positives are embedded into the pack
  as hard negatives — the medical "+negatives" move, automated. Five
  rounds of fresh probes: FPs went **9 → 7 → 3 → 6 → 5**, nineteen
  negatives ingested, each round discovering a new impostor class
  (OSDE-but-billing, free-consult-but-with-conditions).

The verdict the matrix renders on the eight-hour-old pack is the
verdict the system exists to render: **certification withheld** — it
stays in shadow-serve, where its two evidence-promoted intents keep
earning their keep against the live provider while the negative fence
grows. One template per intent and thirty mined positives do not buy a
zero-FP guarantee, and now there is an instrument that says so with
numbers instead of optimism.

The full loop is the standard lifecycle for ANY new domain: shadow
→ distill → **matrix-certify (ingest FPs until clean)** → shadow-serve
→ serve. The benchmark the medical book used to prove a cache *could*
reach 100% is now the gate that decides when each new domain has
earned its zero-dollar turns.
