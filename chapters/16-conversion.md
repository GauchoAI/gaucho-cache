# Valuing the close: the gym's value function comes home

The user named the missing organ precisely: *"how does the gym value
selling closures — if the agent actually manages to end up with a
sale? We must have that; else we risk that the cache only knows two or
three iterations."* Every gate so far measured truthfulness and
coverage. None measured the only number a sales funnel exists for:
**did the customer buy?**

## What we ported from the gym

agentic-crm's gym (`gym/src/gym/runner.py`) doesn't ask an LLM whether
a conversation "went well" — it enforces a deterministic **conversion
trifecta**, checked every turn:

> `would_buy_now_if_offered` AND `stage_out == ACTION` AND payment
> captured with a conversion-eligible method.

The customer walks a 4-stage AIDA FSM (awareness → interest → desire →
action) that can move at most ±1 per turn; outcomes resolve by hard
precedence (CONVERTED > LOST_INTEREST > TIMED_OUT); and the customer's
sentiment JSON — not its prose — is the only ground truth. All of that
is now `scripts/gym_eval.py`, with persona goals straight from the
gym's catalog lineage (`buy_yes_yes`, `buy_cautious`, `browse_maybe` —
the first always asks price and cuotas before paying, like cm02).

## What a domain unlocks: class B

The second half of the user's insight: *"a mock database helps,
because it helps to have a domain."* The PLAN always defined
cacheability class B — audited template + **deterministic** slot-fill —
but without products there was nothing to fill. Now there is:
`data/catalog.json` (ten mattresses in agentic-crm's product shape:
size, firmeza, tecnología, list price, sale flag) and
`data/payment_ladder.json` (the laferia multiplier ladder: efectivo
50% off → 6 cuotas 35% off). On top of them, `gaucho_cache/render.py`:

- **Recommendation** — size is a hard filter, posture maps to firmness
  preference (de costado → blando/medio; boca abajo → firme — the
  laferia scoring axes), sale items break ties. Two products, prices,
  best offer. A catalog lookup.
- **Payment options** — the full ladder for the recommended product,
  cuotas arithmetic included. A multiplication.
- **The close** — chosen method, final price, checkout link with SKU
  and method. String formatting.

None of these turns costs a token. And the close is **slot-gated, not
similarity-gated**: "transferencia" embeds poorly but means exactly one
thing after a recommendation — `detect_payment_choice` fires before the
classifier is even consulted.

`gaucho_cache/serving.py` ties it together as the FSM-lite the
production CRM runs at full size: slots accumulate across turns, the
bot remembers whether it has recommended or offered payments, and acks
*advance* ("dale" after a recommendation serves the payment ladder, not
a generic proceed-nicety).

## The experiment: does the cache help or hurt the sale?

Two arms, same personas, same seeds, same catalog. **Hybrid**: cache
first (class A templates + class B renders), LLM lane for the rest.
**Control**: the same sales brief, pure LLM every turn. Judged by the
trifecta, plus the in-context judge auditing every cached reply.

Two full runs, independent seeds, 24 conversations per arm each:

| run | arm | converted | cached share | bad cached serves |
|---|---|---|---|---|
| seed 7 | hybrid | **8/24 (33%)** | 30% | 0 |
| seed 7 | control | 4/24 (17%) | 0% | 0 |
| seed 21 | hybrid | **10/24 (42%)** | 32% | 0 |
| seed 21 | control | 4/24 (17%) | 0% | 0 |

(Between the runs, the close became slot-gated — `class_b_close` went
from ×1 to ×7, and conversion rose with it.) The hybrid didn't just
match the pure LLM — it **more than doubled its conversion rate**. The reading is almost embarrassing in hindsight: a
deterministic render advances the funnel *every single time*. The
recommendation arrives instantly with concrete products and prices;
the ladder arrives with the cuotas already computed; the close arrives
with a link. The LLM control meanders — warm, plausible, and slower to
put a price in front of the customer. In a sales funnel, **crispness
converts**, and crispness is exactly what a cache is made of.

The cached-turn share tells the depth story the user asked about: the
cache no longer lives only in the first two or three turns. Its lanes
in the seed-21 run: `class_b_recommend ×16, class_b_close ×7,
template ×2, context_discount ×1` — the middle and the END of the
funnel, where the money is.

## What this means for the thesis

The zero-dollar claim was always about turns; this chapter upgrades it
to outcomes. The cache serves the *spine* of the sale — greet, qualify,
recommend, price, close — deterministically, and rents intelligence
only for the meat: objections, edge cases, bespoke requirements. The
gym's value function is now a permanent gate (`gym_eval.py`: hybrid
conversion ≥ control − 10pp AND zero bad cached serves in context),
so no future "improvement" to the cache can quietly trade sales away.
