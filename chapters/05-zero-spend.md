# The zero-spend proof: $0 by construction, not by accounting

A cost claim based on *not observing* API calls is weak — something
could call out in a code path the test missed. The proof here is
constructive: **the process cannot reach the network at all.**

Before any import, `socket.socket.connect` is replaced with a raising
stub, every `*API_KEY*`/`*TOKEN*` environment variable is deleted, and
`HF_HUB_OFFLINE=1` forces the embedding model to load from the local
cache. Then the full runtime path — embed → route → compound predicate
→ template render — runs over the entire held-out evaluation set. One
attempted connection anywhere would crash the run.

{{include:reports/zero-spend-proof.md}}

Two numbers matter beyond the zero:

- **p50 latency ~11 ms** — three orders of magnitude under an LLM
  round-trip. The cache is not just free, it is *instant*, which is its
  own UX win on WhatsApp.
- **Serve-eligible rate** reflects the audit gate, not the classifier:
  template edits made during the quality round reset `audited:false`
  pending human re-review. Routing coverage is higher; serving is
  deliberately throttled by the human-audit pipeline.
