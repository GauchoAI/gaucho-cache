# P0.5 slice evaluation — embedding-only (mini-E2)

- Model: `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`
- Index: 442 train positives + 220 hard negatives; 114 held-out positives evaluated

## Headline (gate: serving accuracy ≥99%, confident_wrong = 0; raw routing informational — social-pair and below-threshold confusions never reach a customer)

| Metric | Value |
|---|---|
| Routing accuracy (top-1, informational) | 86.0% |
| **Serving accuracy (correct intent when served)** | **95.7%** |
| Hit rate (compound predicate) | 40.4% |
| Confident-wrong rate | **1.75%** (2) |
| Adversarial negatives confidently mis-served | 4 / 220 |

## Per intent

| Intent | audited | n | top-1 | hits | confident-wrong |
|---|---|---|---|---|---|
| order_status | ✓ | 34 | 94% | 38% | 0 |
| shipping | ✓ | 23 | 87% | 43% | 0 |
| size_change | ✓ | 33 | 85% | 36% | 1 |
| stock_model | ✓ | 24 | 75% | 46% | 1 |

## Confusable pairs (routing confusions, held-out)

| Pair | a→b | b→a |
|---|---|---|
| shipping_time ↔ shipping_zone | 0 | 0 |
| warranty ↔ return_policy | 0 | 0 |
| size_fit ↔ firmness_doubt | 0 | 0 |
| brand_trust ↔ bot_skepticism | 0 | 0 |

Other confusions: order_status→shipping×1, order_status→size_change×1, shipping→order_status×3, size_change→order_status×1, size_change→shipping×1, size_change→stock_model×3, stock_model→order_status×4, stock_model→size_change×2

## Confident-wrong cases (MUST be zero to pass)

- `Dale, 39?` — true `size_change`, served `stock_model` (0.876)
- `¿Disponible talla 42?` — true `stock_model`, served `size_change` (0.804)

## Adversarial negatives confidently mis-served

- `¿Cuándo reponen los botines de cuero negro? Tengo ganas pero no sé si están en stock.` — not-shipping (actually other), served `stock_model` (0.817)
- `¿Cuándo recargan los modelos de sneakers en color azul? Necesito saber el tiempo.` — not-shipping (actually other), served `stock_model` (0.817)
- `¿Aún está disponible el modelo de sneaker que vi el lunes con la foto del tallaje 42?` — not-size_change (actually other), served `stock_model` (0.825)
- `¿Pueden enviar una foto del interior del zapato antes de comprar?` — not-stock_model (actually other), served `order_status` (0.832)

## Gate: **FAIL**
