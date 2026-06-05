# Sales intelligence, not product data

The cache's combinatorial space is **(stage × intent × sales-move)** —
funnel knowledge, not catalog knowledge. The values cached are
reusable sales moves: reassure, defer unverifiable specifics, ask the
closing question. Product facts (names, prices, sizes, stock) must
never be baked in; they arrive at render time through placeholders
resolved from deterministic sources (catalog DB, WooCommerce, the
order system) — still $0 in LLM spend.

This is enforced mechanically, not by convention: every template body
is swept for price literals, percentage discounts, concrete
delivery/warranty durations, and SKU-like tokens.

{{include:reports/product-agnostic-check.md}}

The practical consequence for new deployments: swapping the catalog
(or the merchant) does not invalidate the cache's sales intelligence.
A new domain reuses the intent taxonomy and the curation recipe;
only the merchant-voice overlay and the utterance corpus regenerate —
a one-time, single-digit-dollar batched job.
