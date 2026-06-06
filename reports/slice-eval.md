# P0.5 slice evaluation — embedding-only (mini-E2)

- Model: `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`
- Index: 936 train positives + 838 hard negatives; 242 held-out positives evaluated

## Headline (gate: accuracy ≥95%, confident_wrong = 0)

| Metric | Value |
|---|---|
| Routing accuracy (top-1) | **95.5%** |
| Hit rate (compound predicate) | 54.5% |
| Confident-wrong rate | **0.00%** (0) |
| Adversarial negatives confidently mis-served | 24 / 838 |

## Per intent

| Intent | audited | n | top-1 | hits | confident-wrong |
|---|---|---|---|---|---|
| bot_skepticism | ✓ | 20 | 100% | 90% | 0 |
| brand_trust | ✗ | 19 | 89% | 68% | 0 |
| firmness_doubt | ✗ | 17 | 88% | 24% | 0 |
| greet | ✓ | 19 | 100% | 42% | 0 |
| out_of_stock_reservation | ✓ | 15 | 93% | 53% | 0 |
| price | ✗ | 19 | 100% | 74% | 0 |
| return_policy | ✗ | 17 | 94% | 12% | 0 |
| shipping_time | ✓ | 18 | 94% | 44% | 0 |
| shipping_zone | ✓ | 19 | 89% | 42% | 0 |
| size_fit | ✗ | 19 | 100% | 53% | 0 |
| thanks_goodbye | ✓ | 19 | 100% | 89% | 0 |
| warranty | ✓ | 21 | 100% | 19% | 0 |
| what_do_you_sell | ✓ | 20 | 90% | 90% | 0 |

## Confusable pairs (routing confusions, held-out)

| Pair | a→b | b→a |
|---|---|---|
| shipping_time ↔ shipping_zone | 0 | 1 |
| warranty ↔ return_policy | 0 | 0 |
| size_fit ↔ firmness_doubt | 0 | 2 |
| brand_trust ↔ bot_skepticism | 0 | 0 |

Other confusions: brand_trust→size_fit×2, out_of_stock_reservation→shipping_time×1, return_policy→price×1, shipping_time→out_of_stock_reservation×1, shipping_zone→greet×1, what_do_you_sell→price×1, what_do_you_sell→return_policy×1

## Adversarial negatives confidently mis-served

- `¿Hay alguna forma de pagar con puntos de fidelidad?` — not-brand_trust (actually other), served `price` (0.830)
- `¿Cuándo reponen los colchones de espuma firme? Necesito saber si habrá disponibilidad pronto.` — not-firmness_doubt (actually other), served `out_of_stock_reservation` (0.871)
- `Quisiera saber cuántas opiniones reales hay de clientes que probaron el colchón firme, ¿pueden compartirlas?` — not-firmness_doubt (actually other), served `brand_trust` (0.794)
- `¿Cuándo es la fecha estimada de entrega del colchón firme que pedí?` — not-firmness_doubt (actually other), served `shipping_time` (0.885)
- `¿Hay opción de pago a 12 cuotas y que la cuota quede firme sin intereses adicionales?` — not-firmness_doubt (actually other), served `price` (0.827)
- `¿Hay opción de retirar el colchón en sucursal?` — not-greet (actually other), served `return_policy` (0.891)
- `¿Se puede pagar en cuotas sin interés?` — not-greet (actually other), served `price` (0.864)
- `¿Tienen stock de colchón doble en color gris?` — not-greet (actually other), served `what_do_you_sell` (0.797)
- `Quisiera saber si puedo usar puntos de fidelidad para comprar el colchón, y cómo sería el proceso de envío.` — not-out_of_stock_reservation (actually other), served `what_do_you_sell` (0.794)
- `¿Se puede pagar en cuotas sin interés y que el envío sea gratuito? Necesito confirmar la logística.` — not-out_of_stock_reservation (actually other), served `price` (0.764)
- `¿Se puede programar la entrega para un día específico? Tengo que estar en casa.` — not-price (actually other), served `shipping_time` (0.764)
- `¿y si llega fallado?` — not-return_policy (actually other), served `warranty` (0.900)
- `¿Puedo usar mi cuenta de Mercado Libre para pagar?` — not-return_policy (actually other), served `brand_trust` (0.761)
- `¿Hay alguna promo si pago con débito?` — not-return_policy (actually other), served `price` (0.796)
- `¿cuándo vuelve a haber stock?` — not-shipping_time (actually other), served `out_of_stock_reservation` (0.914)
- `¿Cuánto tarda la entrega si lo pido hoy? Necesito que llegue antes del viernes, porque la cama está lista.` — not-size_fit (actually other), served `shipping_time` (0.877)
- `¿Cuándo repondrían el colchón de espuma de 140 cm?` — not-thanks_goodbye (actually other), served `out_of_stock_reservation` (0.843)
- `¿Aceptan pago en cuotas sin interés?` — not-thanks_goodbye (actually other), served `price` (0.831)
- `¿El colchón tiene garantía contra hundimientos?` — not-thanks_goodbye (actually other), served `warranty` (0.904)
- `¿Hay stock disponible para entrega mañana?` — not-thanks_goodbye (actually other), served `out_of_stock_reservation` (0.829)

## Gate: **PASS**
