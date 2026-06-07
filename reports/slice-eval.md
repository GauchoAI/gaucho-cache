# P0.5 slice evaluation — embedding-only (mini-E2)

- Model: `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`
- Index: 3580 train positives + 1245 hard negatives; 903 held-out positives evaluated

## Headline (gate: serving accuracy ≥99%, confident_wrong = 0; raw routing informational — social-pair and below-threshold confusions never reach a customer)

| Metric | Value |
|---|---|
| Routing accuracy (top-1, informational) | 86.7% |
| **Serving accuracy (correct intent when served)** | **100.0%** |
| Hit rate (compound predicate) | 41.9% |
| Confident-wrong rate | **0.00%** (0) |
| Adversarial negatives confidently mis-served | 41 / 1245 |

## Per intent

| Intent | audited | n | top-1 | hits | confident-wrong |
|---|---|---|---|---|---|
| answer_for_whom | ✓ | 47 | 72% | 47% | 0 |
| answer_payment_choice | ✓ | 84 | 95% | 6% | 0 |
| answer_size_posture | ✓ | 263 | 95% | 57% | 0 |
| ask_recommendation | ✓ | 29 | 48% | 21% | 0 |
| awaiting_reply | ✓ | 23 | 70% | 4% | 0 |
| bot_skepticism | ✓ | 21 | 81% | 62% | 0 |
| brand_trust | ✗ | 20 | 90% | 55% | 0 |
| confirmation | ✓ | 51 | 82% | 33% | 0 |
| declination | ✓ | 57 | 77% | 72% | 0 |
| firmness_doubt | ✗ | 19 | 89% | 37% | 0 |
| greet | ✓ | 13 | 85% | 77% | 0 |
| order_status | ✓ | 21 | 90% | 76% | 0 |
| out_of_stock_reservation | ✓ | 23 | 83% | 22% | 0 |
| price | ✗ | 31 | 87% | 39% | 0 |
| return_policy | ✗ | 31 | 90% | 23% | 0 |
| shipping_time | ✓ | 28 | 82% | 21% | 0 |
| shipping_zone | ✓ | 22 | 82% | 23% | 0 |
| size_fit | ✗ | 21 | 95% | 19% | 0 |
| thanks_goodbye | ✓ | 21 | 76% | 76% | 0 |
| want_to_buy | ✓ | 23 | 78% | 57% | 0 |
| warranty | ✓ | 35 | 97% | 6% | 0 |
| what_do_you_sell | ✓ | 20 | 85% | 40% | 0 |

## Confusable pairs (routing confusions, held-out)

| Pair | a→b | b→a |
|---|---|---|
| shipping_time ↔ shipping_zone | 1 | 1 |
| warranty ↔ return_policy | 0 | 1 |
| size_fit ↔ firmness_doubt | 0 | 0 |
| brand_trust ↔ bot_skepticism | 0 | 0 |

Other confusions: answer_for_whom→answer_size_posture×4, answer_for_whom→ask_recommendation×4, answer_for_whom→confirmation×1, answer_for_whom→greet×1, answer_for_whom→want_to_buy×3, answer_payment_choice→price×4, answer_size_posture→answer_for_whom×1, answer_size_posture→ask_recommendation×3, answer_size_posture→awaiting_reply×1, answer_size_posture→firmness_doubt×1, answer_size_posture→return_policy×1, answer_size_posture→size_fit×1, answer_size_posture→want_to_buy×4, ask_recommendation→answer_size_posture×12, ask_recommendation→want_to_buy×3, awaiting_reply→confirmation×2, awaiting_reply→declination×3, awaiting_reply→greet×1, awaiting_reply→thanks_goodbye×1, bot_skepticism→confirmation×3, bot_skepticism→greet×1, brand_trust→price×1, brand_trust→what_do_you_sell×1, confirmation→answer_for_whom×1, confirmation→answer_payment_choice×3, confirmation→awaiting_reply×1, confirmation→greet×1, confirmation→thanks_goodbye×1, confirmation→want_to_buy×1, confirmation→warranty×1, declination→answer_for_whom×1, declination→awaiting_reply×2, declination→bot_skepticism×1, declination→confirmation×3, declination→firmness_doubt×2, declination→out_of_stock_reservation×1, declination→price×1, declination→thanks_goodbye×2, firmness_doubt→answer_size_posture×2, greet→size_fit×1, greet→thanks_goodbye×1, order_status→awaiting_reply×1, order_status→out_of_stock_reservation×1, out_of_stock_reservation→answer_payment_choice×2, out_of_stock_reservation→confirmation×1, out_of_stock_reservation→order_status×1, price→answer_payment_choice×1, price→declination×1, price→out_of_stock_reservation×1, price→return_policy×1, return_policy→declination×1, return_policy→out_of_stock_reservation×1, shipping_time→confirmation×1, shipping_time→declination×1, shipping_time→out_of_stock_reservation×2, shipping_zone→answer_for_whom×2, shipping_zone→order_status×1, size_fit→answer_size_posture×1, thanks_goodbye→awaiting_reply×3, thanks_goodbye→declination×2, want_to_buy→answer_for_whom×1, want_to_buy→answer_size_posture×4, warranty→out_of_stock_reservation×1, what_do_you_sell→answer_size_posture×1, what_do_you_sell→size_fit×2

## Adversarial negatives confidently mis-served

- `¿Tienen reseñas de clientes reales sobre el colchón?` — not-answer_for_whom (actually other), served `brand_trust` (0.771)
- `¿Me pueden indicar la hora estimada de entrega?` — not-answer_for_whom (actually other), served `shipping_time` (0.877)
- `¿Cuál es el tiempo de entrega estimado?` — not-answer_for_whom (actually other), served `shipping_time` (0.926)
- `para mi hermano, que sea liviano y facil de mover` — not-answer_for_whom (actually other), served `answer_size_posture` (0.854)
- `¿Se pueden pagar cuotas sin interés pero que el envío sea a domicilio?` — not-answer_payment_choice (actually other), served `price` (0.867)
- `¿Cuál es la política de devoluciones si lo pago con transferencia y no me gusta?` — not-answer_payment_choice (actually other), served `return_policy` (0.885)
- `¿Cuál es la política de devolución si el colchón no me gusta después de probarlo?` — not-answer_size_posture (actually other), served `return_policy` (0.913)
- `¿Me contestó una máquina? Quisiera saber si aceptan pago por transferencia bancaria.` — not-bot_skepticism (actually other), served `price` (0.814)
- `¿Puedo abonar con efectivo al momento de la entrega?` — not-brand_trust (actually other), served `confirmation` (0.873)
- `¿Hay alguna forma de pagar con puntos de fidelidad?` — not-brand_trust (actually other), served `price` (0.821)
- `Si, pero el colchón no me gustó, quiero devolverlo.` — not-confirmation (actually other), served `return_policy` (0.883)
- `Dale, pero ¿cuál es el tiempo de envío estimado?` — not-confirmation (actually other), served `shipping_time` (0.915)
- `Si, pero ¿pueden enviarme opiniones de clientes reales?` — not-confirmation (actually other), served `brand_trust` (0.856)
- `Dale, pero ¿cuál es la política de cambios?` — not-confirmation (actually other), served `return_policy` (0.904)
- `Dale, pero me gustaría saber la política de devoluciones.` — not-confirmation (actually other), served `return_policy` (0.895)
- `¿Se puede abonar con efectivo al entrega?` — not-declination (actually other), served `confirmation` (0.882)
- `¿Puedo ver opiniones de clientes reales?` — not-declination (actually other), served `brand_trust` (0.820)
- `¿Puedo usar cupones de descuento?` — not-declination (actually other), served `price` (0.888)
- `¿Hay disponible el modelo en color gris?` — not-declination (actually other), served `out_of_stock_reservation` (0.855)
- `¿Cuál es la política de devoluciones?` — not-declination (actually other), served `return_policy` (0.903)

## Gate: **PASS**
