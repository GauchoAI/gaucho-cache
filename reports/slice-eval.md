# P0.5 slice evaluation — embedding-only (mini-E2)

- Model: `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`
- Index: 715 train positives + 673 hard negatives; 184 held-out positives evaluated

## Headline (gate: accuracy ≥95%, confident_wrong = 0)

| Metric | Value |
|---|---|
| Routing accuracy (top-1) | **95.7%** |
| Hit rate (compound predicate) | 52.2% |
| Confident-wrong rate | **0.00%** (0) |
| Adversarial negatives confidently mis-served | 11 / 673 |

## Per intent

| Intent | audited | n | top-1 | hits | confident-wrong |
|---|---|---|---|---|---|
| bot_skepticism | ✓ | 20 | 100% | 90% | 0 |
| brand_trust | ✗ | 19 | 89% | 68% | 0 |
| firmness_doubt | ✗ | 17 | 88% | 24% | 0 |
| out_of_stock_reservation | ✓ | 15 | 93% | 53% | 0 |
| price | ✗ | 19 | 100% | 79% | 0 |
| return_policy | ✗ | 17 | 94% | 12% | 0 |
| shipping_time | ✓ | 18 | 100% | 61% | 0 |
| shipping_zone | ✓ | 19 | 95% | 42% | 0 |
| size_fit | ✗ | 19 | 100% | 63% | 0 |
| warranty | ✓ | 21 | 95% | 24% | 0 |

## Confusable pairs (routing confusions, held-out)

| Pair | a→b | b→a |
|---|---|---|
| shipping_time ↔ shipping_zone | 0 | 1 |
| warranty ↔ return_policy | 1 | 0 |
| size_fit ↔ firmness_doubt | 0 | 2 |
| brand_trust ↔ bot_skepticism | 0 | 0 |

Other confusions: brand_trust→size_fit×2, out_of_stock_reservation→shipping_time×1, return_policy→price×1

## Adversarial negatives confidently mis-served

- `¿Hay alguna forma de pagar con puntos de fidelidad?` — not-brand_trust (actually other), served `price` (0.830)
- `¿Cuándo reponen los colchones de espuma firme? Necesito saber si habrá disponibilidad pronto.` — not-firmness_doubt (actually other), served `out_of_stock_reservation` (0.871)
- `Quisiera saber cuántas opiniones reales hay de clientes que probaron el colchón firme, ¿pueden compartirlas?` — not-firmness_doubt (actually other), served `brand_trust` (0.794)
- `¿Cuándo es la fecha estimada de entrega del colchón firme que pedí?` — not-firmness_doubt (actually other), served `shipping_time` (0.885)
- `¿Hay opción de pago a 12 cuotas y que la cuota quede firme sin intereses adicionales?` — not-firmness_doubt (actually other), served `price` (0.827)
- `¿Se puede pagar en cuotas sin interés y que el envío sea gratuito? Necesito confirmar la logística.` — not-out_of_stock_reservation (actually other), served `price` (0.764)
- `¿y si llega fallado?` — not-return_policy (actually other), served `warranty` (0.900)
- `¿Puedo usar mi cuenta de Mercado Libre para pagar?` — not-return_policy (actually other), served `brand_trust` (0.761)
- `¿Hay alguna promo si pago con débito?` — not-return_policy (actually other), served `price` (0.796)
- `¿cuándo vuelve a haber stock?` — not-shipping_time (actually other), served `out_of_stock_reservation` (0.914)
- `¿Cuánto tarda la entrega si lo pido hoy? Necesito que llegue antes del viernes, porque la cama está lista.` — not-size_fit (actually other), served `shipping_time` (0.877)

## Gate: **PASS**
