# P0.5 slice evaluation — embedding-only (mini-E2)

- Model: `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`
- Index: 715 train positives + 317 hard negatives; 184 held-out positives evaluated

## Headline (gate: accuracy ≥95%, confident_wrong = 0)

| Metric | Value |
|---|---|
| Routing accuracy (top-1) | **95.7%** |
| Hit rate (compound predicate) | 62.5% |
| Confident-wrong rate | **0.00%** (0) |
| Adversarial negatives confidently mis-served | 4 / 317 |

## Per intent

| Intent | audited | n | top-1 | hits | confident-wrong |
|---|---|---|---|---|---|
| bot_skepticism | ✓ | 20 | 100% | 95% | 0 |
| brand_trust | ✗ | 19 | 89% | 74% | 0 |
| firmness_doubt | ✗ | 17 | 88% | 47% | 0 |
| out_of_stock_reservation | ✓ | 15 | 93% | 53% | 0 |
| price | ✗ | 19 | 100% | 84% | 0 |
| return_policy | ✓ | 17 | 94% | 18% | 0 |
| shipping_time | ✓ | 18 | 100% | 89% | 0 |
| shipping_zone | ✓ | 19 | 95% | 47% | 0 |
| size_fit | ✗ | 19 | 100% | 89% | 0 |
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

- `¿Puedo pagar con Mercado Pago y que me cuadren los puntos del programa de fidelidad?` — not-out_of_stock_reservation (actually other), served `price` (0.795)
- `¿Aceptan pagos con Mercado Pago? Vi que hay una promo, pero no sé si puedo usar mis puntos.` — not-out_of_stock_reservation (actually other), served `price` (0.751)
- `¿y si llega fallado?` — not-return_policy (actually other), served `warranty` (0.900)
- `¿cuándo vuelve a haber stock?` — not-shipping_time (actually other), served `out_of_stock_reservation` (0.914)

## Gate: **PASS**
