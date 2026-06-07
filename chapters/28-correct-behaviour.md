# Correct behaviour: what "done" actually means for a $0 cache

Chasing 80% served at $0, I kept measuring one number — served-AND-
correct — and treating every forwarded turn as a failure. This chapter
is the correction, and it redefines the goal honestly.

## The full 2×2

A turn has four possible fates, not two. The cache either serves or
forwards; either choice is right or wrong:

| | correct | wrong |
|---|---|---|
| **served** | served-and-correct ($0, true) | **a lie** (floor breach) |
| **forwarded** | correctly forwarded (genuinely novel) | missed (templatable, recall debt) |

Measured on the held-out 30% of real COCO traffic:

```
CORRECT BEHAVIOUR (served-right + forwarded-rightly): 79/124 = 64%
  ├─ served at $0, correct ............ 52
  ├─ forwarded, correctly (novel) ..... 27
  ├─ LIES (served wrong) .............. 5    ← floor = 0
  └─ MISSED (templatable, forwarded) .. 40   ← recall debt
$0 ceiling = templatable share ........ 74% of real traffic
```

The reframe matters because **a $0 cache that forwards a genuinely
novel turn is behaving correctly** — the forward costs cents and is the
*right call*. Reading the real forwarded traffic confirms it: deep
fit consultations ("la horma del California, calzo 23,3"), one-off
problems, conversational glue ("perdón", "pruebo más tarde con la
compu"), media attachments. Serving a template to those would be a
lie. They *should* forward.

## What this does to the goal

The 80% target was a guess at the templatable share. The judge now
measures it: **~74% of real traffic is templatable**; the rest
genuinely needs a live agent. So the honest completion criterion is not
"80% served no matter what." It is three numbers:

1. **Lies → 0** (the floor; currently 5 — the un-certified-serving debt
   of chapter 26, fixable offline).
2. **$0 share → the templatable ceiling** (~74%; currently 42% — the
   recall debt of 40 turns).
3. **Correct behaviour → ~100%** (currently 64%): serve where
   templatable, forward where novel, never lie.

"Acts exactly like Cerebras or better" is precisely this: on the novel
74%-complement the cache *does* call Cerebras (correctly forwarded); on
the templatable 74% it must match-or-beat it at $0. The goal is not to
template the un-templatable — it is to template all of the templatable
and forward the rest, honestly.

## The named distance to completion

The 40 missed templatable turns decompose cleanly:

- **greeting-masked service** ("Holaa, alguna novedad?" → routed
  greeting) — salutation decomposition into the service cluster
  recovers some (applied this chapter, +net serves).
- **mid-conversation fragments** ("elegí Correo Argentino", "es el
  único día que estoy a esa hora") — need real dialogue-state, not a
  word-count proxy (the lesson of ch. 27's reverted heuristic).
- **two unbuilt flows** — store-hours ("¿en qué horario se puede
  retirar?") and payment-info ("¿a qué precio quedan en efectivo?") —
  small, templatable, deliberately deferred.
- **below-threshold service turns** — need denser real-seed coverage so
  they clear the bar without the threshold being lowered into lies.

Session arc, honestly stated: served-AND-correct **23% → 42%**, lies
**31 → 5**, and — the number that reframes the rest — **correct
behaviour 64%** against a **74% $0 ceiling**, with the remaining work
enumerated, not hand-waved. The goal didn't move; the meaning of
finishing it got precise.
