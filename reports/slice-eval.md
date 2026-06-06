# P0.5 slice evaluation — embedding-only (mini-E2)

- Model: `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`
- Index: 937 train positives + 909 hard negatives; 241 held-out positives evaluated

## Headline (gate: serving accuracy ≥99%, confident_wrong = 0; raw routing informational — social-pair and below-threshold confusions never reach a customer)

| Metric | Value |
|---|---|
| Routing accuracy (top-1, informational) | 92.5% |
| **Serving accuracy (correct intent when served)** | **100.0%** |
| Hit rate (compound predicate) | 51.5% |
| Confident-wrong rate | **0.00%** (0) |
| Adversarial negatives confidently mis-served | 22 / 909 |

## Per intent

| Intent | audited | n | top-1 | hits | confident-wrong |
|---|---|---|---|---|---|
| bot_skepticism | ✓ | 19 | 84% | 68% | 0 |
| brand_trust | ✗ | 19 | 89% | 74% | 0 |
| firmness_doubt | ✗ | 17 | 88% | 24% | 0 |
| greet | ✓ | 14 | 93% | 64% | 0 |
| order_status | ✓ | 3 | 67% | 67% | 0 |
| out_of_stock_reservation | ✓ | 15 | 73% | 33% | 0 |
| price | ✗ | 19 | 100% | 84% | 0 |
| return_policy | ✗ | 17 | 94% | 12% | 0 |
| shipping_time | ✓ | 19 | 100% | 42% | 0 |
| shipping_zone | ✓ | 19 | 95% | 58% | 0 |
| size_fit | ✗ | 19 | 95% | 42% | 0 |
| thanks_goodbye | ✓ | 21 | 100% | 86% | 0 |
| warranty | ✓ | 21 | 100% | 19% | 0 |
| what_do_you_sell | ✓ | 19 | 89% | 53% | 0 |

## Confusable pairs (routing confusions, held-out)

| Pair | a→b | b→a |
|---|---|---|
| shipping_time ↔ shipping_zone | 0 | 1 |
| warranty ↔ return_policy | 0 | 0 |
| size_fit ↔ firmness_doubt | 1 | 2 |
| brand_trust ↔ bot_skepticism | 0 | 0 |

Other confusions: bot_skepticism→greet×2, bot_skepticism→shipping_zone×1, brand_trust→firmness_doubt×1, brand_trust→size_fit×1, greet→thanks_goodbye×1, order_status→out_of_stock_reservation×1, out_of_stock_reservation→order_status×1, out_of_stock_reservation→return_policy×1, out_of_stock_reservation→shipping_time×2, return_policy→price×1, what_do_you_sell→firmness_doubt×1, what_do_you_sell→size_fit×1

## Adversarial negatives confidently mis-served

- `Quiero pagar en 12 cuotas sin interés, ¿es posible?` — not-brand_trust (actually other), served `price` (0.808)
- `¿Hay alguna forma de pagar con puntos de fidelidad?` — not-brand_trust (actually other), served `price` (0.821)
- `¿Cuándo reponen los colchones de espuma firme? Necesito saber si habrá disponibilidad pronto.` — not-firmness_doubt (actually other), served `out_of_stock_reservation` (0.871)
- `Quisiera saber cuántas opiniones reales hay de clientes que probaron el colchón firme, ¿pueden compartirlas?` — not-firmness_doubt (actually other), served `brand_trust` (0.794)
- `¿Cuándo es la fecha estimada de entrega del colchón firme que pedí?` — not-firmness_doubt (actually other), served `shipping_time` (0.885)
- `¿Hay opción de pago a 12 cuotas y que la cuota quede firme sin intereses adicionales?` — not-firmness_doubt (actually other), served `price` (0.804)
- `¿Hay opción de retirar el colchón en sucursal?` — not-greet (actually other), served `return_policy` (0.891)
- `¿Se puede pagar en cuotas sin interés?` — not-greet (actually other), served `price` (0.878)
- `¿Se puede pagar en cuotas sin interés y que el envío sea gratuito? Necesito confirmar la logística.` — not-out_of_stock_reservation (actually other), served `price` (0.799)
- `¿Se puede programar la entrega para un día específico? Tengo que estar en casa.` — not-price (actually other), served `shipping_time` (0.764)
- `¿y si llega fallado?` — not-return_policy (actually other), served `warranty` (0.900)
- `¿Puedo usar mi cuenta de Mercado Libre para pagar?` — not-return_policy (actually other), served `brand_trust` (0.761)
- `¿Hay alguna promo si pago con débito?` — not-return_policy (actually other), served `price` (0.781)
- `¿cuándo vuelve a haber stock?` — not-shipping_time (actually other), served `out_of_stock_reservation` (0.914)
- `¿Cuánto tarda la entrega si lo pido hoy? Necesito que llegue antes del viernes, porque la cama está lista.` — not-size_fit (actually other), served `shipping_time` (0.877)
- `¿Cuándo repondrían el colchón de espuma de 140 cm?` — not-thanks_goodbye (actually other), served `out_of_stock_reservation` (0.843)
- `¿Aceptan pago en cuotas sin interés?` — not-thanks_goodbye (actually other), served `price` (0.831)
- `¿El colchón tiene garantía contra hundimientos?` — not-thanks_goodbye (actually other), served `warranty` (0.904)
- `¿Hay stock disponible para entrega mañana?` — not-thanks_goodbye (actually other), served `out_of_stock_reservation` (0.829)
- `¿Aceptan puntos de fidelidad de otras marcas?` — not-what_do_you_sell (actually other), served `brand_trust` (0.767)

## Gate: **PASS**
