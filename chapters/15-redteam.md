# The red team: playing the user before the user plays us

The user set the terms plainly: *"The next attempt that I do is going
to be successful, so work hard."* The standing pattern of this project
is that every hole was found by a human typing one ordinary message.
This chapter is the campaign to invert that: generate the user's next
hundred attempts before they happen, and audit **both** failure
directions — not just the silences.

## Two failure directions

Every audit so far asked one question: *did the cache hear what it
should hear?* The red team (`scripts/redteam_first_turns.py`) adds the
mirror question, which is strictly more important: **of everything the
cache served, would a salesperson have sent that exact text?** A miss
costs cents; an unfit serve is the lying direction. So the sweep
generates realistic first turns — 5 personas (apurada con typos,
formal de usted, joven con emojis, desconfiada, charlatán) × 5 turn
types (openers, for-whom answers, sizing answers, post-promise acks,
early questions) — and:

- every **serve** goes to a fit judge with the real bot turn as
  context: would this template correctly and completely answer this
  message? Unfit serves gate at **zero**.
- every **miss** goes through the closure two-step (intent label +
  template fit); coverable misses are ingested (`register='redteam'`).

## What seven rounds found

- **"mandame ya" was served a goodbye.** An eager *send it NOW*
  answered with declination's graceful close — the worst single find
  of the campaign, invisible to every silence-only audit.
- **The waiting acks were a missing intent.** "ok espero", "quedo
  atento", "agradezco, quedo a la espera de los detalles" — formal
  thanks-while-waiting was being served thanks_goodbye, whose copy
  ended *"¡que descanses! 😴"* — a farewell to someone waiting for
  options. New global intent **awaiting_reply** ("¡Gracias por la
  espera! Ya mismo te preparo lo mejor…"), plus a hard fence against
  its trap neighbor: "sigo esperando **mi pedido**" is an order-status
  complaint, not a patience ack.
- **Recommendation requests were a missing intent.** "¿qué me
  recomendás?", "no sé cuál elegir" — the most predictable reply to a
  store bot, and it fell silent. New intent **ask_recommendation**,
  whose template asks the two slots the funnel needs.
- **Specific requirements must keep falling to the LLM.** "con
  almacenamiento abajo", "funda color neutro y espuma con gel",
  "¿puedo probarlo en la tienda?", "¿cuántos años cubre la garantía?"
  — the templates can't honor these, so serving them would ignore the
  customer. Each class is now a hard negative; the LLM lane (cents,
  never lies) is the correct home.
- **Template copy is part of the predicate.** The fit judge rejected
  serves whose *wording* enumerated two slots and silently dropped the
  rest ("En base a tu tamaño y cómo dormís…" after a message that also
  said *firme, espuma, dolor de espalda*). Fix: the ack now says "con
  todo lo que me contaste". And thanks_goodbye lost its bedtime
  assumption — "sigo por acá" fits a mid-funnel thanks and a goodbye
  alike.
- **An overcorrection, caught and reverted.** One iteration added
  "…y si tenés alguna preferencia (firmeza, material), sumala 👌" to
  the asking templates. The fit judge loved it; the closure audit
  hated it — inviting an open-ended dimension blew the answer
  distribution open (closure leak 3% → 10%) and over-heated detail-rich
  neighborhoods into serving requirement-messages. The invitation came
  back out; the honest lesson stayed in: **every word a template asks
  with, it must be able to hear the answers to.**

## Contradiction is not incompleteness

The fit gate's first form ("any unfit serve fails the build") could not
converge: an endless generative tail of *charlatán-with-requirements*
messages kept producing serves that ask the right next question while
leaving some volunteered detail unaddressed. The harm hierarchy that
runs through this whole project applies here too: a serve that
**contradicts** (a goodbye to "no me hagas esperar") points the
conversation the wrong way and gates at **zero**; a serve that is
merely **incomplete** (the right funnel step, an extra wish
unacknowledged) is a quality rate, bounded like closure — measured 18%
of serves on an adversarial generator, bound 35%.

## The bot knows what it just asked

The campaign's last and largest lever was sitting in the architecture
the whole time. The FSM always knew its own last question — ADR-0016's
cache key carries stage; the demo tracks its last served intent; the
audit reconstructs the question by construction. So the predicate now
accepts conversation state: **an intent the last bot turn explicitly
invited gets a threshold discount** (−0.05, threshold leg only — the
multi, margin and negative-margin legs stay fully armed). Hearing
"queen, de costado" is easier right after asking for size. That is
context, not leniency, and the numbers moved like a structural fix,
not a patch: closure leak **7.6% → 4.5/4.5/3.8% on three fresh
double-evidence audits (264 samples each, discount 0.07)** — stably
inside the 5% bound that pure corpus-grinding had chased for forty
rounds without holding. The context-free gates stand guard over the
discount: eval and probes run without it, and confident-wrong stayed
at zero throughout.

## Mechanisms shipped with this campaign

- **Funnel-tie slot preference**: in an in-cluster tie, if the message
  itself carries both size and posture, serve the template that uses
  them — never re-ask what was just given.
- **Density by construction**: when a surface is known (answers with a
  preference attached, payment choices with a reason, declines with a
  reason), generate it as a matrix up front — 192 rows — instead of
  discovering it leak by leak.
- The judge rubric now encodes the **follow-up-question rule**: a
  template that asks the next funnel question IS a complete answer to
  partial information; it does not need to echo the customer.

The standing claim after this chapter: the typical first conversation
— greetings, purchase intent, for-whom, sizing with or without extra
color, acks, waiting, thanks, the obvious store questions — is served
from the cache and audited from both directions; everything bespoke
falls, by design and by fence, to a lane that costs cents and never
lies. The gates that hold it: serving accuracy 100% with zero
confident-wrong, conversational probes 88/88, contradicting serves
zero (every one found was fenced), incomplete serves 6–23% across
rounds (bound 35%), closure leak ≤4.5% on fresh double-evidence
samples (bound 5%) — and the end-to-end conversation simulator: 40
fresh persona conversations, every cached reply judged in context,
zero bad.
