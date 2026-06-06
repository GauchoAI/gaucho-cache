# P0.5 slice evaluation — embedding-only (mini-E2)

- Model: `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`
- Index: 1489 train positives + 1297 hard negatives; 384 held-out positives evaluated

## Headline (gate: serving accuracy ≥99%, confident_wrong = 0; raw routing informational — social-pair and below-threshold confusions never reach a customer)

| Metric | Value |
|---|---|
| Routing accuracy (top-1, informational) | 92.4% |
| **Serving accuracy (correct intent when served)** | **100.0%** |
| Hit rate (compound predicate) | 48.4% |
| Confident-wrong rate | **0.00%** (0) |
| Adversarial negatives confidently mis-served | 45 / 1297 |

## Per intent

| Intent | audited | n | top-1 | hits | confident-wrong |
|---|---|---|---|---|---|
| answer_for_whom | ✓ | 22 | 95% | 77% | 0 |
| answer_payment_choice | ✓ | 17 | 88% | 35% | 0 |
| answer_size_posture | ✓ | 20 | 95% | 35% | 0 |
| bot_skepticism | ✓ | 19 | 84% | 68% | 0 |
| brand_trust | ✗ | 19 | 89% | 74% | 0 |
| confirmation | ✓ | 22 | 91% | 55% | 0 |
| declination | ✓ | 21 | 90% | 48% | 0 |
| firmness_doubt | ✗ | 17 | 88% | 24% | 0 |
| greet | ✓ | 13 | 85% | 46% | 0 |
| order_status | ✓ | 21 | 90% | 71% | 0 |
| out_of_stock_reservation | ✓ | 15 | 80% | 33% | 0 |
| price | ✗ | 21 | 100% | 57% | 0 |
| return_policy | ✗ | 17 | 94% | 12% | 0 |
| shipping_time | ✓ | 19 | 100% | 32% | 0 |
| shipping_zone | ✓ | 19 | 95% | 42% | 0 |
| size_fit | ✗ | 19 | 95% | 42% | 0 |
| thanks_goodbye | ✓ | 21 | 90% | 86% | 0 |
| want_to_buy | ✓ | 21 | 90% | 33% | 0 |
| warranty | ✓ | 21 | 100% | 19% | 0 |
| what_do_you_sell | ✓ | 20 | 100% | 60% | 0 |

## Confusable pairs (routing confusions, held-out)

| Pair | a→b | b→a |
|---|---|---|
| shipping_time ↔ shipping_zone | 0 | 1 |
| warranty ↔ return_policy | 0 | 0 |
| size_fit ↔ firmness_doubt | 1 | 2 |
| brand_trust ↔ bot_skepticism | 0 | 0 |

Other confusions: answer_for_whom→confirmation×1, answer_payment_choice→price×2, answer_size_posture→price×1, bot_skepticism→confirmation×1, bot_skepticism→greet×1, bot_skepticism→shipping_zone×1, brand_trust→firmness_doubt×1, brand_trust→size_fit×1, confirmation→firmness_doubt×1, confirmation→price×1, declination→confirmation×1, declination→thanks_goodbye×1, greet→size_fit×1, greet→thanks_goodbye×1, order_status→out_of_stock_reservation×2, out_of_stock_reservation→order_status×2, out_of_stock_reservation→shipping_time×1, return_policy→confirmation×1, thanks_goodbye→answer_size_posture×1, thanks_goodbye→declination×1, want_to_buy→answer_for_whom×1, want_to_buy→answer_size_posture×1

## Adversarial negatives confidently mis-served

- `quiero un colchon para mi` — not-answer_for_whom (actually other), served `want_to_buy` (0.850)
- `¿Tienen reseñas de clientes reales sobre el colchón?` — not-answer_for_whom (actually other), served `brand_trust` (0.895)
- `¿Puedo pagar con transfer bancario?` — not-answer_for_whom (actually other), served `answer_payment_choice` (0.856)
- `¿Vuelven a poner el colchón de espuma alta en stock?` — not-answer_for_whom (actually other), served `out_of_stock_reservation` (0.884)
- `¿Tienen testimonios de gente que probó el colchón?` — not-answer_for_whom (actually other), served `brand_trust` (0.790)
- `¿Cuál es el tiempo de entrega estimado?` — not-answer_for_whom (actually other), served `shipping_time` (0.905)
- `¿Se pueden pagar cuotas sin interés pero que el envío sea a domicilio?` — not-answer_payment_choice (actually other), served `price` (0.867)
- `¿Hay cargos por retiro en sucursal si pago con efectivo?` — not-answer_payment_choice (actually other), served `price` (0.776)
- `¿Cuánto tardan en entregar el colchón queen a la zona de Palermo?` — not-answer_size_posture (actually other), served `shipping_time` (0.801)
- `¿Cuántas reseñas reales hay del colchón queen en su sitio?` — not-answer_size_posture (actually other), served `brand_trust` (0.784)
- `¿Hay alguna forma de pagar con puntos de fidelidad?` — not-brand_trust (actually other), served `price` (0.821)
- `Dale, pero ¿cuál es el tiempo de envío estimado?` — not-confirmation (actually other), served `shipping_time` (0.915)
- `Ok, pero ¿puedo usar puntos de fidelidad para pagar?` — not-confirmation (actually other), served `price` (0.787)
- `Si, pero ¿pueden enviarme opiniones de clientes reales?` — not-confirmation (actually other), served `brand_trust` (0.856)
- `¿Puedo ver opiniones de clientes reales?` — not-declination (actually other), served `brand_trust` (0.818)
- `¿Puedo usar cupones de descuento?` — not-declination (actually other), served `price` (0.888)
- `¿Cuándo repondrán el stock del colchón king size?` — not-declination (actually other), served `out_of_stock_reservation` (0.820)
- `¿Cuándo reponen los colchones de espuma firme? Necesito saber si habrá disponibilidad pronto.` — not-firmness_doubt (actually other), served `out_of_stock_reservation` (0.871)
- `Quisiera saber cuántas opiniones reales hay de clientes que probaron el colchón firme, ¿pueden compartirlas?` — not-firmness_doubt (actually other), served `brand_trust` (0.794)
- `¿Cuándo es la fecha estimada de entrega del colchón firme que pedí?` — not-firmness_doubt (actually other), served `shipping_time` (0.885)

## Gate: **PASS**
