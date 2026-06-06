# Battle test — wave 6, independent simulated traffic

- Traffic: **9918** messages (7458 in-taxonomy, 2460 novelty: payment/off-topic/compound)
- Decision stack: full compound predicate + match contracts + audit gate (production rules)

## Headline

| Metric | Value | 95% CI |
|---|---|---|
| Serve rate (overall) | 12.4% | |
| Shadow coverage (incl. unaudited/precondition hits) | 20.7% | |
| **Confirmed wrong serves** | **14 / 1227 (1.14%)** | 0.68%–1.91% |
| False-serves on novelty traffic | 1 / 2460 (0.04%) | |
| Apparent wrongs that were generator mislabels | 56 / 70 | |

## By concern

| Concern | n | served | correct serve | confirmed wrong |
|---|---|---|---|---|
| bot_skepticism | 679 | 332 | 332 | 0 |
| brand_trust | 460 | 9 | 0 | 1 |
| compound | 820 | 1 | 0 | 1 |
| firmness_doubt | 739 | 0 | 0 | 0 |
| greet | 680 | 252 | 225 | 6 |
| off_topic | 860 | 12 | 0 | 0 |
| out_of_stock_reservation | 560 | 11 | 0 | 2 |
| payment_method | 780 | 0 | 0 | 0 |
| price | 740 | 1 | 0 | 1 |
| return_policy | 480 | 2 | 0 | 1 |
| shipping_time | 720 | 150 | 150 | 0 |
| shipping_zone | 440 | 88 | 86 | 2 |
| size_fit | 540 | 0 | 0 | 0 |
| thanks_goodbye | 400 | 296 | 296 | 0 |
| warranty | 520 | 22 | 22 | 0 |
| what_do_you_sell | 500 | 51 | 46 | 0 |

## Confirmed wrong serves (corpus-fix queue)

- `tenes resenas reales?` — served `bot_skepticism`, generator said `brand_trust`, judge says `brand_trust`
- `si tardan mucho en enviar el colchón me quedo sin cama y también me inquieta que la garant` — served `shipping_time`, generator said `compound`, judge says `compound`
- `buen día si pueden contestar` — served `thanks_goodbye`, generator said `greet`, judge says `greet`
- `hola hay alguien en el chat` — served `bot_skepticism`, generator said `greet`, judge says `greet`
- `que tal hay alguien para conversar?` — served `bot_skepticism`, generator said `greet`, judge says `greet`
- `buenas noches hay alguien` — served `thanks_goodbye`, generator said `greet`, judge says `greet`
- `Buenas noches, xfa, alguien?` — served `thanks_goodbye`, generator said `greet`, judge says `greet`
- `buen día necesitaba iniciar conversación` — served `bot_skepticism`, generator said `greet`, judge says `greet`
- `¿Cuándo llega de nuevo el modelo Queen?` — served `shipping_time`, generator said `out_of_stock_reservation`, judge says `out_of_stock_reservation`
- `¿Hay fecha estimada de llegada del modelo Queen? Tengo una oferta que expira pronto.` — served `shipping_time`, generator said `out_of_stock_reservation`, judge says `out_of_stock_reservation`
- `¡Rebaja ya!` — served `thanks_goodbye`, generator said `price`, judge says `price`
- `¿Tienen servicio de recogida en mi barrio para la devolución? 🤞` — served `shipping_zone`, generator said `return_policy`, judge says `return_policy`
- `Necesito que el colchón llegue antes del fin de mes tienen cobertura allí` — served `shipping_time`, generator said `shipping_zone`, judge says `compound`
- `quiero saber el tiempo de entrega si llegan a mi sector de la zona sur` — served `shipping_time`, generator said `shipping_zone`, judge says `compound`

Ledger after audit: $22.82