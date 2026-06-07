# P0.5 slice evaluation — embedding-only (mini-E2)

- Model: `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`
- Index: 3604 train positives + 1245 hard negatives; 914 held-out positives evaluated

## Headline (gate: serving accuracy ≥99%, confident_wrong = 0; raw routing informational — social-pair and below-threshold confusions never reach a customer)

| Metric | Value |
|---|---|
| Routing accuracy (top-1, informational) | 86.5% |
| **Serving accuracy (correct intent when served)** | **100.0%** |
| Hit rate (compound predicate) | 32.6% |
| Confident-wrong rate | **0.00%** (0) |
| Adversarial negatives confidently mis-served | 42 / 1245 |

## Per intent

| Intent | audited | n | top-1 | hits | confident-wrong |
|---|---|---|---|---|---|
| answer_for_whom | ✓ | 48 | 69% | 42% | 0 |
| answer_payment_choice | ✓ | 84 | 94% | 6% | 0 |
| answer_size_posture | ✓ | 263 | 95% | 27% | 0 |
| ask_recommendation | ✓ | 29 | 45% | 14% | 0 |
| awaiting_reply | ✓ | 23 | 70% | 0% | 0 |
| bot_skepticism | ✓ | 21 | 81% | 62% | 0 |
| brand_trust | ✗ | 20 | 85% | 65% | 0 |
| confirmation | ✓ | 52 | 77% | 48% | 0 |
| declination | ✓ | 57 | 77% | 65% | 0 |
| firmness_doubt | ✗ | 20 | 85% | 20% | 0 |
| greet | ✓ | 13 | 85% | 77% | 0 |
| order_status | ✓ | 22 | 86% | 68% | 0 |
| out_of_stock_reservation | ✓ | 24 | 79% | 38% | 0 |
| price | ✗ | 31 | 81% | 35% | 0 |
| return_policy | ✗ | 32 | 94% | 6% | 0 |
| shipping_time | ✓ | 29 | 97% | 17% | 0 |
| shipping_zone | ✓ | 23 | 91% | 30% | 0 |
| size_fit | ✗ | 22 | 91% | 23% | 0 |
| thanks_goodbye | ✓ | 21 | 86% | 71% | 0 |
| want_to_buy | ✓ | 23 | 78% | 57% | 0 |
| warranty | ✓ | 36 | 97% | 11% | 0 |
| what_do_you_sell | ✓ | 21 | 95% | 48% | 0 |

## Confusable pairs (routing confusions, held-out)

| Pair | a→b | b→a |
|---|---|---|
| shipping_time ↔ shipping_zone | 0 | 1 |
| warranty ↔ return_policy | 0 | 1 |
| size_fit ↔ firmness_doubt | 1 | 2 |
| brand_trust ↔ bot_skepticism | 0 | 0 |

Other confusions: answer_for_whom→answer_size_posture×5, answer_for_whom→ask_recommendation×4, answer_for_whom→confirmation×2, answer_for_whom→greet×1, answer_for_whom→want_to_buy×3, answer_payment_choice→declination×1, answer_payment_choice→price×4, answer_size_posture→answer_for_whom×2, answer_size_posture→ask_recommendation×4, answer_size_posture→price×1, answer_size_posture→size_fit×2, answer_size_posture→want_to_buy×3, ask_recommendation→answer_for_whom×1, ask_recommendation→answer_size_posture×11, ask_recommendation→want_to_buy×4, awaiting_reply→confirmation×2, awaiting_reply→declination×2, awaiting_reply→greet×1, awaiting_reply→shipping_time×1, awaiting_reply→thanks_goodbye×1, bot_skepticism→confirmation×2, bot_skepticism→greet×1, bot_skepticism→shipping_zone×1, brand_trust→ask_recommendation×1, brand_trust→firmness_doubt×1, brand_trust→size_fit×1, confirmation→answer_for_whom×1, confirmation→answer_payment_choice×3, confirmation→answer_size_posture×1, confirmation→bot_skepticism×1, confirmation→declination×2, confirmation→return_policy×1, confirmation→want_to_buy×1, confirmation→warranty×2, declination→answer_payment_choice×3, declination→answer_size_posture×1, declination→confirmation×1, declination→out_of_stock_reservation×1, declination→price×3, declination→return_policy×2, declination→shipping_time×2, firmness_doubt→answer_size_posture×1, greet→size_fit×1, greet→thanks_goodbye×1, order_status→awaiting_reply×1, order_status→declination×1, order_status→shipping_zone×1, out_of_stock_reservation→declination×1, out_of_stock_reservation→order_status×2, out_of_stock_reservation→shipping_time×1, out_of_stock_reservation→shipping_zone×1, price→answer_payment_choice×4, price→ask_recommendation×1, price→what_do_you_sell×1, return_policy→confirmation×1, shipping_time→answer_for_whom×1, shipping_zone→confirmation×1, size_fit→ask_recommendation×1, thanks_goodbye→answer_size_posture×1, thanks_goodbye→awaiting_reply×1, thanks_goodbye→declination×1, want_to_buy→answer_for_whom×1, want_to_buy→answer_size_posture×4, warranty→answer_size_posture×1, what_do_you_sell→warranty×1

## Adversarial negatives confidently mis-served

- `¿Tienen reseñas de clientes reales sobre el colchón?` — not-answer_for_whom (actually other), served `brand_trust` (0.895)
- `¿Me pueden indicar la hora estimada de entrega?` — not-answer_for_whom (actually other), served `shipping_time` (0.900)
- `¿Vuelven a poner el colchón de espuma alta en stock?` — not-answer_for_whom (actually other), served `out_of_stock_reservation` (0.884)
- `¿Tienen testimonios de gente que probó el colchón?` — not-answer_for_whom (actually other), served `brand_trust` (0.790)
- `¿Cuál es el tiempo de entrega estimado?` — not-answer_for_whom (actually other), served `shipping_time` (0.926)
- `¿Se pueden pagar cuotas sin interés pero que el envío sea a domicilio?` — not-answer_payment_choice (actually other), served `price` (0.867)
- `¿Cuál es la política de devolución si el colchón no me gusta después de probarlo?` — not-answer_size_posture (actually other), served `return_policy` (0.908)
- `¿Cuántas reseñas reales hay del colchón queen en su sitio?` — not-answer_size_posture (actually other), served `brand_trust` (0.784)
- `¿Me contestó una máquina? Quisiera saber si aceptan pago por transferencia bancaria.` — not-bot_skepticism (actually other), served `price` (0.814)
- `¿Hay alguna forma de pagar con puntos de fidelidad?` — not-brand_trust (actually other), served `price` (0.821)
- `Dale, pero ¿cuál es el tiempo de envío estimado?` — not-confirmation (actually other), served `shipping_time` (0.915)
- `Si, pero ¿pueden enviarme opiniones de clientes reales?` — not-confirmation (actually other), served `brand_trust` (0.856)
- `Dale, pero ¿cuál es la política de cambios?` — not-confirmation (actually other), served `return_policy` (0.904)
- `Dale, pero me gustaría saber la política de devoluciones.` — not-confirmation (actually other), served `return_policy` (0.909)
- `¿Puedo ver opiniones de clientes reales?` — not-declination (actually other), served `brand_trust` (0.818)
- `¿Puedo usar cupones de descuento?` — not-declination (actually other), served `price` (0.888)
- `¿Hay disponible el modelo en color gris?` — not-declination (actually other), served `out_of_stock_reservation` (0.855)
- `¿Cuál es la política de devoluciones?` — not-declination (actually other), served `return_policy` (0.903)
- `¿Cuándo repondrán el stock del colchón king size?` — not-declination (actually other), served `out_of_stock_reservation` (0.820)
- `¿Cuándo reponen los colchones de espuma firme? Necesito saber si habrá disponibilidad pronto.` — not-firmness_doubt (actually other), served `out_of_stock_reservation` (0.871)

## Gate: **PASS**
