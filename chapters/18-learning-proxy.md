# The learning proxy: hook up any agent, watch the API calls die

The user asked the architectural question that decides whether this
project is a benchmark or a product: *"Do we connect it to any agent,
no matter what? We'll have sales agents, receptionist agents… how can
we make a system we just hook up — hitting Cerebras or Codex or OpenAI
— and over time it showcases that it no longer needs to invoke the
API?"*

Everything before this chapter was machinery wrapped around
hand-seeded data: a mattress taxonomy, authored templates, a curated
catalog. The machinery was always domain-agnostic (chapter 11 ported
it to shoes with a YAML); the data never was. This chapter removes the
last hand-written artifact — the taxonomy itself — and answers the
hook-up question literally.

## The shape: an OpenAI-compatible layer

`gaucho_cache/proxy.py` speaks chat-completions — the dialect Cerebras,
OpenAI and Codex all share. An agent points its `base_url` at the proxy
and changes nothing else; the agent never learns the proxy exists. Per
domain, the proxy walks a lifecycle:

1. **Shadow** — every call forwards to the provider; the proxy logs
   (conversation state, user turn, provider reply). Cost: unchanged.
2. **Distill** (`scripts/distill_traffic.py`) — the existing judges run
   on the logs. Recurring user turns cluster into intents (salutations
   stripped first; a coherence judge rejects mixed clusters and keeps
   names stable across runs). For each intent, the provider's most
   central reply becomes the template candidate — audited by a
   REUSABILITY judge: could this exact text answer every message in
   the cluster, every time, with nothing per-customer in it? The
   provider is the unwitting author of its own replacement.
3. **Shadow-serve** — the cache decides every turn; the provider still
   answers. Each would-be serve is judged against the provider's
   actual reply (standalone sufficiency, not stylistic identity), and
   templates accrue EVIDENCE.
4. **Serve** — a template that earns its bar (4+ agreements, ≤20%
   disagreement) flips live: the provider goes silent on that intent.
   Misses still forward; every miss is future corpus. The ratchet only
   tightens.

## The experiment: a domain this repo had never seen

A dental-clinic receptionist — no corpus, no templates, no taxonomy,
no catalog. Patient personas (book a cleaning, ask hours, OSDE
coverage, prices, address) call through the proxy into Cerebras.
Distillation runs between cycles. Nine cycles end to end:

| phase | cached share | what happened |
|---|---|---|
| cycles 1–5 | 0% | pure shadow; taxonomy mined from nothing to 7 intents (`ask_business_hours`, `request_clinic_address_and_directions`, `inquire_osde_coverage`, `ask_first_consultation_free`…) while evidence accumulated |
| cycle 6 | 0% | last evidence short of the bar |
| cycle 7 | **46%** | `inquire_osde_coverage` (5/0) and `ask_first_consultation_free` (4/1) promote and start serving |
| cycles 8–9 | 9% / 16% | noisy small samples — booking-heavy mixes forward more, by design |

The served replies are sentences the live agent itself wrote days
(cycles) earlier, judged reusable, evidence-gated, now costing $0:

> Cliente: *"¡Hola! ¿Me atienden con OSDE? Gracias, saludos."*
> Caché: *"¡Sí, te atendemos con OSDE! ¿Me podés decir tu nombre y la
> franja horaria que prefieres? Te anoto y te envío el recordatorio
> por acá."*

## The refusal is the feature

The most important row in the evidence table is the one that never
promoted: `thank_and_farewell` — **19 agreements, 31 disagreements**.
Farewells looked clusterable, but the live agent's goodbyes carry
context (a booking just confirmed, a name); serving a canned one would
sometimes be wrong, so the evidence gate starved it out. Bookings
themselves — all per-patient specifics — never even produced a
reusable template candidate. The curve climbs on the surface that IS a
template and refuses the surface that isn't. **Cache the spine, rent
the meat** — now learned from traffic instead of designed by hand.

## What production adds

The mattress chapters are the picture of this domain pack at maturity:
hand-audit on top of evidence (the `audited` flag generalizes to
"evidence + optional human sign-off"), hard negatives mined from
disagreements, the closure loop running on the mined templates' own
questions, class-B renders once a merchant wires its facts (catalog,
ladder, hours) into slots, and the conversion/Turing gates as the
permanent quality floor. None of that machinery needed changing — the
proxy feeds it the one thing it always required and never had to
invent: real traffic.
