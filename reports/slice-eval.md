# P0.5 slice evaluation — embedding-only (mini-E2)

- Model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- Index: 760 train positives + 200 hard negatives; 200 held-out positives evaluated

## Headline (gate: accuracy ≥95%, confident_wrong = 0)

| Metric | Value |
|---|---|
| Routing accuracy (top-1) | **87.0%** |
| Hit rate (compound predicate) | 79.5% |
| Confident-wrong rate | **3.00%** (6) |
| Adversarial negatives confidently mis-served | 23 / 200 |

## Per intent

| Intent | audited | n | top-1 | hits | confident-wrong |
|---|---|---|---|---|---|
| bot_skepticism | ✓ | 20 | 100% | 100% | 0 |
| brand_trust | ✗ | 20 | 95% | 85% | 1 |
| firmness_doubt | ✗ | 20 | 75% | 85% | 2 |
| out_of_stock_reservation | ✓ | 20 | 80% | 75% | 1 |
| price | ✗ | 20 | 90% | 90% | 0 |
| return_policy | ✓ | 20 | 75% | 70% | 1 |
| shipping_time | ✓ | 20 | 80% | 80% | 1 |
| shipping_zone | ✓ | 20 | 95% | 75% | 0 |
| size_fit | ✗ | 20 | 85% | 65% | 0 |
| warranty | ✓ | 20 | 95% | 70% | 0 |

## Confusable pairs (routing confusions, held-out)

| Pair | a→b | b→a |
|---|---|---|
| shipping_time ↔ shipping_zone | 1 | 0 |
| warranty ↔ return_policy | 0 | 3 |
| size_fit ↔ firmness_doubt | 2 | 2 |
| brand_trust ↔ bot_skepticism | 0 | 0 |

Other confusions: brand_trust→warranty×1, firmness_doubt→bot_skepticism×1, firmness_doubt→warranty×2, out_of_stock_reservation→return_policy×1, out_of_stock_reservation→shipping_time×2, out_of_stock_reservation→size_fit×1, price→firmness_doubt×1, price→size_fit×1, return_policy→bot_skepticism×1, return_policy→size_fit×1, shipping_time→out_of_stock_reservation×3, shipping_zone→firmness_doubt×1, size_fit→return_policy×1, warranty→size_fit×1

## Confident-wrong cases (MUST be zero to pass)

- `¿Tienen garantía?` — true `brand_trust`, served `warranty` (0.960)
- `Che, ¿duro?` — true `firmness_doubt`, served `size_fit` (0.966)
- `¿Cómo puedo saber si la cama será lo suficientemente suave para descansar?` — true `firmness_doubt`, served `size_fit` (0.722)
- `Lo reservo?` — true `out_of_stock_reservation`, served `shipping_time` (0.762)
- `Q pasa dev?` — true `return_policy`, served `bot_skepticism` (0.895)
- `Quisiera confirmar la fecha estimada de llegada del colchón, pues tengo una mudanza programada para el próximo mes y no puedo esperar.` — true `shipping_time`, served `out_of_stock_reservation` (0.802)

## Adversarial negatives confidently mis-served

- `¿Cuándo llega la promo? No me fío de los bots que cambian los precios a mitad de la noche.` — not-bot_skepticism (actually other), served `out_of_stock_reservation` (0.651)
- `Quiero saber si el tamaño del colchón coincide con mi cama, pero la respuesta automática no me ayuda.` — not-bot_skepticism (actually other), served `size_fit` (0.829)
- `Me gustaría saber si aceptan pagos en efectivo al recibir, porque los bots solo hablan de tarjetas.` — not-bot_skepticism (actually other), served `brand_trust` (0.689)
- `¿Hay algún descuento por comprar dos colchones? El bot me dejó con dudas porque parece automático.` — not-bot_skepticism (actually other), served `price` (0.707)
- `¿Cuál es el tiempo de entrega para la zona de Palermo? Necesito saber si llegan antes del fin de mes.` — not-brand_trust (actually other), served `shipping_time` (0.894)
- `Quiero saber si el colchón tiene garantía de 10 años, ¿me pueden mandar el detalle?` — not-brand_trust (actually other), served `warranty` (0.705)
- `¿Puedo probar el colchón antes de comprarlo? Necesito estar seguro de la comodidad.` — not-brand_trust (actually other), served `firmness_doubt` (0.684)
- `¿Puedo pagar en cuotas sin interés? Vi que la descripción menciona “soft financing”.` — not-firmness_doubt (actually other), served `price` (0.723)
- `Quería confirmar si el precio en la web incluye el costo del envío o si hay cargos extra.` — not-out_of_stock_reservation (actually other), served `brand_trust` (0.656)
- `¿Se puede pagar en cuotas sin interés? Necesito saber si el banco lo aprueba.` — not-out_of_stock_reservation (actually other), served `price` (0.804)
- `Estoy viendo el colchón y me preocupa la política de devoluciones: ¿puedo devolverlo si no me gusta?` — not-out_of_stock_reservation (actually other), served `return_policy` (0.725)
- `¿Puedo pagar con Mercado Pago y que me cuadren los puntos del programa de fidelidad?` — not-out_of_stock_reservation (actually other), served `price` (0.711)
- `¿Cuál es la política de devoluciones? No me convence la idea de no poder cambiarlo si no me gusta.` — not-price (actually other), served `return_policy` (0.639)
- `¿Se puede armar el colchón en cualquier habitación o necesita espacio especial?` — not-price (actually other), served `size_fit` (0.688)
- `¿Puedo pagar en cuotas sin interés o me vuelven a cobrar intereses después?` — not-return_policy (actually other), served `price` (0.842)
- `¿Cual es el tiempo estimado de entrega a Capital? Necesito saber si llega antes del feriado.` — not-return_policy (actually other), served `shipping_time` (0.649)
- `¿Hay descuentos por comprar dos colchones al mismo tiempo?` — not-return_policy (actually other), served `price` (0.642)
- `¿Puedo pagar en cuotas sin interés con la tarjeta, o solo con efectivo al momento de la entrega?` — not-shipping_time (actually other), served `price` (0.858)
- `Quiero saber si el envío incluye la instalación del colchón, y cuánto tardará el montaje.` — not-shipping_zone (actually other), served `shipping_time` (0.695)
- `Si el pedido llega dañado, ¿cómo hacen la devolución? Necesito saber el proceso.` — not-shipping_zone (actually other), served `return_policy` (0.808)

## Gate: **FAIL**
