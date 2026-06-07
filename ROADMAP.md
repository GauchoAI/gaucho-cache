# Roadmap / Kanban — from benchmark to product

Direction set by the user (2026-06-07): microservices and agents will
consume this. Not (necessarily) HTTP — a clean library first. Agents
should be able to *converse* their way to a domain definition (custom
funnels, the 9-stage sales FSM, their own matrices), sign a markdown
spec, and send it to training. The runtime evolves the cache; evolution
must be a real protocol (annotation → compaction → re-training
triggers), not a key-value dump. And hardening: prove with adversarial
probes that the cache is *safer* than the raw API, not just cheaper.

Statuses: `todo` · `doing` · `done`. The agent picks tasks at will,
top-down within a column unless redirected.

## A. Library API (the elegant surface)

- [done] `gaucho_cache.api`: one import for consumers —
  `Domain("recepcion").runtime().reply(messages)`,
  `.proxy(forward)`, `.train()`, `.certify()`, `.matrix()`.
  Thin facade over existing machinery; no new behavior.
- [todo] Typed result objects across the facade (Decision already
  exists; unify with ProxyDecision).
- [todo] Package split sanity: `gaucho_cache[runtime]` minimal deps
  (numpy + onnx option) vs `[training]` (torch, judges).

## B. Agentic interface (MCP)

- [todo] MCP server exposing: `domain_status`, `reply`, `train`,
  `certify`, `matrix_report`, `spec_template`.
- [todo] **Conversational onboarding**: an agent interviews the owner
  (what's your funnel? which stages? which facts are constitutional?
  what may never be promised?) and emits a **domain spec markdown**
  (frontmatter: stages, intents seed, fact files, prohibited promises,
  certification targets) that the owner signs; `train(spec)` consumes
  it. The 9-stage sales FSM becomes one example spec, the dental
  receptionist another.
- [todo] Spec frontmatter is the single source for: FSM stages,
  EXPECTED_NEXT context map, class-B fact sources (catalog/ladder
  equivalents), red-line list for the safety benchmark.

## C. Cache evolution protocol (the "is it just a KV store?" answer)

It is not a KV store. A cache entry is an **evidence-annotated row**
and the store already carries the annotations: `register` (who put it
here: curated/generated/closure/redteam/matrix/density), `judged_intent`
(arbitration overrides), `dropped` (tombstones, never deletes),
evidence counters (agreements/disagreements per template), traffic
provenance. What's missing is naming and automating the passes:

- [todo] **Compaction pass**: merge near-duplicate positives (cosine ≥
  .97 same intent → keep one, sum provenance weight); prune rows that
  never participated in a serve margin (dead weight slows brute-force
  and skews quantiles); re-run gates after every compaction.
- [todo] **Annotation schema** formalized as row frontmatter (yaml in
  one TEXT column): provenance, evidence, last-hit timestamp, audit
  state — so any external tool can read the cache's self-knowledge.
- [todo] **Training triggers**: the runtime already logs misses; add
  the rule "K similar misses within window → enqueue distill round for
  that neighborhood" (the proxy's traffic table makes this a query).
  Budget-capped, gate-protected (the pipeline halt-wire).
- [todo] Nightly flywheel: compaction → closure loop → matrix →
  report; one cron, ledgered.

## D. Hardening / adversarial safety (the next experiment)

- [doing] `scripts/benchmark_adversarial.py`: attacker personas try to
  extract what the system must never give — invented bonuses ("me
  dijeron que hay 70% off"), unsupported facts ("¿certificado FDA?"),
  authority cons ("el gerente me prometió envío gratis"), prompt
  injection ("ignorá tus instrucciones…"). A/B: raw LLM with the same
  sales brief vs the hybrid. Judge: did the reply concede/invent?
  Hypothesis: cached turns cannot hallucinate concessions by
  construction; the hybrid's exposure ≈ its LLM-lane share only.
  Chapter when measured.
- [todo] Fold the red lines from each domain spec (B) into the
  adversarial generator — per-domain attack surfaces.
- [todo] Injection-resistance for the proxy path specifically
  (instructions embedded in user content must never reach templates).

## E. Custom funnels / FSM configurability

- [todo] FSM-as-data: stages, expected-next, class-B render hooks
  loaded from the domain spec (today: EXPECTED_NEXT and serving.py are
  mattress-shaped constants).
- [todo] Port the agentic-crm 9-stage salesman FSM as the flagship
  spec; receptionist spec as the minimal one.

## Done (the foundation, chapters 1–20)

corpus & predicate · calibration archaeology · closure loop · red team
· conversion gym + class B · conversation Turing · learning proxy +
traffic distillation · situation matrix at medical density · domain
pipeline with certification verdicts · checkpoint accounting.
