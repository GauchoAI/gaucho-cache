# P0.5 slice evaluation — embedding-only (mini-E2)

- Model: `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`
- Index: 2069 train positives + 1190 hard negatives; 528 held-out positives evaluated

## Headline (gate: serving accuracy ≥99%, confident_wrong = 0; raw routing informational — social-pair and below-threshold confusions never reach a customer)

| Metric | Value |
|---|---|
| Routing accuracy (top-1, informational) | 91.1% |
| **Serving accuracy (correct intent when served)** | **100.0%** |
| Hit rate (compound predicate) | 48.7% |
| Confident-wrong rate | **0.00%** (0) |
| Adversarial negatives confidently mis-served | 52 / 1190 |

## Per intent

| Intent | audited | n | top-1 | hits | confident-wrong |
|---|---|---|---|---|---|
| answer_for_whom | ✓ | 29 | 90% | 66% | 0 |
| answer_payment_choice | ✓ | 45 | 91% | 13% | 0 |
| answer_size_posture | ✓ | 79 | 95% | 41% | 0 |
| bot_skepticism | ✓ | 21 | 81% | 62% | 0 |
| brand_trust | ✗ | 19 | 89% | 74% | 0 |
| confirmation | ✓ | 39 | 87% | 69% | 0 |
| declination | ✓ | 36 | 86% | 78% | 0 |
| firmness_doubt | ✗ | 19 | 84% | 21% | 0 |
| greet | ✓ | 13 | 85% | 69% | 0 |
| order_status | ✓ | 21 | 90% | 71% | 0 |
| out_of_stock_reservation | ✓ | 15 | 80% | 33% | 0 |
| price | ✗ | 23 | 91% | 52% | 0 |
| return_policy | ✗ | 20 | 95% | 10% | 0 |
| shipping_time | ✓ | 23 | 100% | 26% | 0 |
| shipping_zone | ✓ | 20 | 90% | 30% | 0 |
| size_fit | ✗ | 20 | 95% | 40% | 0 |
| thanks_goodbye | ✓ | 21 | 90% | 90% | 0 |
| want_to_buy | ✓ | 21 | 90% | 71% | 0 |
| warranty | ✓ | 24 | 100% | 21% | 0 |
| what_do_you_sell | ✓ | 20 | 100% | 60% | 0 |

## Confusable pairs (routing confusions, held-out)

| Pair | a→b | b→a |
|---|---|---|
| shipping_time ↔ shipping_zone | 0 | 2 |
| warranty ↔ return_policy | 0 | 0 |
| size_fit ↔ firmness_doubt | 1 | 2 |
| brand_trust ↔ bot_skepticism | 0 | 0 |

Other confusions: answer_for_whom→answer_size_posture×1, answer_for_whom→confirmation×1, answer_for_whom→return_policy×1, answer_payment_choice→declination×1, answer_payment_choice→price×3, answer_size_posture→price×1, answer_size_posture→want_to_buy×3, bot_skepticism→confirmation×2, bot_skepticism→greet×1, bot_skepticism→shipping_zone×1, brand_trust→firmness_doubt×1, brand_trust→size_fit×1, confirmation→answer_payment_choice×1, confirmation→bot_skepticism×1, confirmation→return_policy×1, confirmation→thanks_goodbye×1, confirmation→warranty×1, declination→answer_payment_choice×1, declination→out_of_stock_reservation×1, declination→price×1, declination→shipping_time×1, declination→thanks_goodbye×1, firmness_doubt→return_policy×1, greet→size_fit×1, greet→thanks_goodbye×1, order_status→out_of_stock_reservation×2, out_of_stock_reservation→order_status×2, out_of_stock_reservation→shipping_time×1, price→answer_payment_choice×1, price→want_to_buy×1, return_policy→confirmation×1, thanks_goodbye→answer_size_posture×1, thanks_goodbye→declination×1, want_to_buy→answer_for_whom×1, want_to_buy→answer_size_posture×1

## Adversarial negatives confidently mis-served

- `quiero un colchon para mi` — not-answer_for_whom (actually other), served `want_to_buy` (0.850)
- `¿Tienen reseñas de clientes reales sobre el colchón?` — not-answer_for_whom (actually other), served `brand_trust` (0.895)
- `¿Me pueden indicar la hora estimada de entrega?` — not-answer_for_whom (actually other), served `shipping_time` (0.877)
- `¿Puedo pagar con transfer bancario?` — not-answer_for_whom (actually other), served `answer_payment_choice` (0.856)
- `¿Vuelven a poner el colchón de espuma alta en stock?` — not-answer_for_whom (actually other), served `out_of_stock_reservation` (0.884)
- `¿Tienen testimonios de gente que probó el colchón?` — not-answer_for_whom (actually other), served `brand_trust` (0.790)
- `¿Cuál es el tiempo de entrega estimado?` — not-answer_for_whom (actually other), served `shipping_time` (0.926)
- `¿Se pueden pagar cuotas sin interés pero que el envío sea a domicilio?` — not-answer_payment_choice (actually other), served `price` (0.867)
- `¿Hay cargos por retiro en sucursal si pago con efectivo?` — not-answer_payment_choice (actually other), served `price` (0.776)
- `¿Cuánto tardan en entregar el colchón queen a la zona de Palermo?` — not-answer_size_posture (actually other), served `shipping_time` (0.801)
- `¿Cuántas reseñas reales hay del colchón queen en su sitio?` — not-answer_size_posture (actually other), served `brand_trust` (0.784)
- `¿Hay alguna forma de pagar con puntos de fidelidad?` — not-brand_trust (actually other), served `price` (0.821)
- `Dale, pero ¿cuál es el tiempo de envío estimado?` — not-confirmation (actually other), served `shipping_time` (0.915)
- `Si, pero ¿pueden enviarme opiniones de clientes reales?` — not-confirmation (actually other), served `brand_trust` (0.856)
- `Dale, pero me gustaría saber la política de devoluciones.` — not-confirmation (actually other), served `return_policy` (0.909)
- `¿Puedo ver opiniones de clientes reales?` — not-declination (actually other), served `brand_trust` (0.818)
- `¿Puedo usar cupones de descuento?` — not-declination (actually other), served `price` (0.888)
- `¿Cuál es la política de devoluciones?` — not-declination (actually other), served `return_policy` (0.903)
- `¿Cuándo repondrán el stock del colchón king size?` — not-declination (actually other), served `out_of_stock_reservation` (0.820)
- `¿Cuándo reponen los colchones de espuma firme? Necesito saber si habrá disponibilidad pronto.` — not-firmness_doubt (actually other), served `out_of_stock_reservation` (0.871)

## Gate: **PASS**
