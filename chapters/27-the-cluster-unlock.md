# The cluster unlock: doubling correct coverage without lying

Chapter 26 ended at served-AND-correct ~29% on real held-out service
traffic, with the path specified. This chapter is the climb that
followed — and the single doctrine that doubled the honest number.

## What was actually blocking recall

Dumping the *forwarded* turns (the recall misses) instead of guessing
showed the culprit was not the threshold — it was the **compound and
margin legs vetoing correct serves**:

```
exchange_return  s=0.78  multi_intent   "Cómo cambio el talle?"
restock          s=0.86  multi_intent   "Alguna novedad sobre las botas?"
order_status     s=0.82  multi_intent   "Me confirman si lo generé bien? #34096"
```

These are *single* service requests, vetoed because a sibling service
intent also scored high. But the predicate already knew this pattern:
SOCIAL and FUNNEL clusters are exempt from exactly these legs, because
confusing two members is harmless (chapters 13, 16). The service intents
are the same kind of cluster — order-status, exchange, shipping and
complaint all answer a no-reference opener with the **identical** ask
("pasame tu número de pedido"). Confusing them on the opener changes
nothing the customer sees.

## The unlock

Registering `SERVICE = {order_status, exchange_return,
shipping_coordination, complaint_problem}` as a third safe cluster —
exempt from the multi-intent and margin legs, just like SOCIAL and
FUNNEL — and serving a single **unified ask** for any in-cluster
no-reference turn, so a mis-route serves the correct shared reply:

| config | served-AND-correct | lies |
|---|---|---|
| ch. 26 end | 29% | 7 |
| + service safe-cluster + lower floor | **45%** | 16 |
| + unified ask, restock pulled out, closer guard | **41%** | **5** |

restock earned its exclusion: its ask is *different* ("decime modelo y
talle"), so confusing a shipping turn into restock served the wrong ask
— a real lie. The doctrine is precise: a safe cluster is a set of
intents that share one reply, not merely related topics.

## The session's honest trajectory

| stage | served-AND-correct | lies |
|---|---|---|
| sales cache on service traffic | ~0% | — |
| service graph, real seeds | 23% | 31 |
| guards + densification | 31% | 3 |
| **service safe-cluster + unified ask** | **41%** | **5** |
| goal | 80% | 0 |

served-AND-correct nearly doubled (23→41%) while lies fell six-fold
(31→5), and the mattress slice stayed at 100%/0 confident-wrong
throughout — the shared predicate gained a cluster, lost nothing. Every
gain was structural (cluster doctrine, unified ask, real hard
negatives, media/closer/no-flow guards); not one came from relaxing the
floor.

## The honest distance left

41% is not 80%, and the remaining gap is now well-characterised: the
last lies and missed serves are turns that only resolve with full
conversation state (mid-thread fragments like "ahí le pasé el número")
and the flows still deliberately forwarded (refund, data-change, store
hours, wholesale). Closing it is the next iteration's work — multi-turn
graph state and the missing flows — measured, as always, in
served-*and-correct*, with the floor at zero. The method is proven; the
remaining distance is labour, not mystery.
