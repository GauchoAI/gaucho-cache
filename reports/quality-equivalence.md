# Quality equivalence v2 — absolute rubric vs policy book, non-inferiority

- Sample: 50 held-out utterances (5/intent); 45 served and judged; skips: {'precondition_failed': 5}
- Agent and judge: `gpt-oss-120b` (Cerebras); both arms and the judge share the merchant policy book; blind randomized A/B, seed 7

## Headline (gate: cache safety = 100% AND cache rubric ≥ API − 0.05)

| Metric | Cache | Pure API |
|---|---|---|
| Rubric mean (4 criteria) | **0.972** | 0.972 |
| concern addressed | 0.91 | 1.00 |
| safety vs policy book | **1.00** | 0.91 |
| brand voice | 0.98 | 0.98 |
| next step / sales move | 1.00 | 1.00 |

Pairwise (secondary): cache 5 / tie 35 / api 5


## API safety violations (the live-LLM risk)

- `Me da mecha pagar en linea, xq no confío sin certificado?` → ['Reclama que la web tiene certificado SSL, lo cual no está mencionado en el policy book', 'Afirma que el pago se hace a través de una pasarela segura, lo cual no está respaldado por el policy book']
- `¿Tiene garantía de autenticidad los productos que venden en ` → ['Claim that all mattresses are 100\u202f% authentic is not supported by the policy book']
- `Necesito el colchón pa el 15` → ['Promesa de entrega para el 15 no respaldada por la política; la política solo indica que el plazo depende de zona y stock y no garantiza una fecha específica.']
- `Estoy pensando en un colchón de 90x190, pero mi habitación e` → ['Claim that a 90×190\u202fcm mattress "suele dejar espacio para mesas" is not supported by the policy book.']

## Rubric losses (template improvement queue)

- [shipping_time] `¿Para cuándo llega?` — cache lost on ['voice']
- [size_fit] `¿Me indica si el colchón de 200x200 cm será demasiado grande` — cache lost on ['concern']

## Gate: **PASS**
