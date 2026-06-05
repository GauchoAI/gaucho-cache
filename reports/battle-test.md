# Battle test — wave 5, independent simulated traffic

- Traffic: **19918** messages (15058 in-taxonomy, 4860 novelty: payment/off-topic/compound)
- Decision stack: full compound predicate + match contracts + audit gate (production rules)

## Headline

| Metric | Value | 95% CI |
|---|---|---|
| Serve rate (overall) | 7.2% | |
| Shadow coverage (incl. unaudited/precondition hits) | 18.2% | |
| **Confirmed wrong serves** | **17 / 1426 (1.19%)** | 0.75%–1.90% |
| False-serves on novelty traffic | 7 / 4860 (0.14%) | |
| Apparent wrongs that were generator mislabels | 98 / 115 | |

## By concern

| Concern | n | served | correct serve | confirmed wrong |
|---|---|---|---|---|
| bot_skepticism | 1359 | 671 | 670 | 1 |
| brand_trust | 1560 | 25 | 0 | 1 |
| compound | 1640 | 12 | 0 | 6 |
| firmness_doubt | 1380 | 0 | 0 | 0 |
| off_topic | 1580 | 42 | 0 | 1 |
| out_of_stock_reservation | 1740 | 27 | 0 | 6 |
| payment_method | 1640 | 0 | 0 | 0 |
| price | 1640 | 0 | 0 | 0 |
| return_policy | 1560 | 4 | 0 | 1 |
| shipping_time | 1359 | 328 | 327 | 1 |
| shipping_zone | 1380 | 226 | 226 | 0 |
| size_fit | 1520 | 0 | 0 | 0 |
| warranty | 1560 | 91 | 88 | 0 |

## Confirmed wrong serves (corpus-fix queue)

- `puede alguien humano decirme cuanto tarda la entrega` — served `shipping_time`, generator said `bot_skepticism`, judge says `compound`
- `¿A quién puedo llamar para confirmar la empresa?` — served `bot_skepticism`, generator said `brand_trust`, judge says `brand_trust`
- `¿Podrían aclararme el plazo de entrega y cuáles son los casos excluidos de la garantía?` — served `warranty`, generator said `compound`, judge says `compound`
- `xq tardan tanto el envio y si puedo devulver?` — served `shipping_time`, generator said `compound`, judge says `compound`
- `quiero saber si hay opciones de financiamiento y si la entrega se hace en la zona este de ` — served `shipping_zone`, generator said `compound`, judge says `compound`
- `¿El precio incluye garantía y, si la garantía falla, cuál es el proceso de sustitución?` — served `warranty`, generator said `compound`, judge says `compound`
- `¿Puedo probar el colchón antes de comprar y qué implica la garantía?` — served `warranty`, generator said `compound`, judge says `compound`
- `¿Precio garantía?` — served `warranty`, generator said `compound`, judge says `price`
- `Quiero confirmar la disponibilidad del modelo XL en Rosario.` — served `shipping_zone`, generator said `off_topic`, judge says `off_topic`
- `Cuanto tiempo más va a estar sin disponibilidad el modelo king que vi ayer` — served `shipping_time`, generator said `out_of_stock_reservation`, judge says `out_of_stock_reservation`
- `¡Mirá, ya lo vi y está agotado! ¿Cuándo llega? 😩` — served `shipping_time`, generator said `out_of_stock_reservation`, judge says `compound`
- `Estoy en Córdoba y me gustaría saber si hacen envíos cuando vuelva el artículo` — served `shipping_zone`, generator said `out_of_stock_reservation`, judge says `compound`
- `Agradecería que me confirmen por escrito el plazo exacto de disponibilidad.` — served `shipping_time`, generator said `out_of_stock_reservation`, judge says `out_of_stock_reservation`
- `Necesito saber exacto en cuántos días vuelve el modelo de colchón queen 25 cm porque tengo` — served `shipping_time`, generator said `out_of_stock_reservation`, judge says `out_of_stock_reservation`
- `Me interesa la versión king, ¿habrá stock antes del mes que viene?` — served `shipping_time`, generator said `out_of_stock_reservation`, judge says `out_of_stock_reservation`
- `¿Tienen garantía de devolución, xfa?` — served `warranty`, generator said `return_policy`, judge says `return_policy`
- `¿Hay envío exprés disponible?` — served `shipping_zone`, generator said `shipping_time`, judge says `shipping_time`

Ledger after audit: $7.50