# Product-agnosticism check — cached values are sales moves

| Template | audited | placeholders | product-specific literals |
|---|---|---|---|
| BOT_SKEPTICISM-v1 | ✓ | — (pure sales move) | **none** |
| BRAND_TRUST-v1 | ✗ | — (pure sales move) | **none** |
| FIRMNESS_DOUBT-v1 | ✗ | — (pure sales move) | **none** |
| OUT_OF_STOCK_RESERVATION-v1 | ✓ | — (pure sales move) | **none** |
| PRICE-v1 | ✗ | — (pure sales move) | **none** |
| RETURN_POLICY-v1 | ✓ | — (pure sales move) | **none** |
| SHIPPING_TIME-v1 | ✓ | — (pure sales move) | **none** |
| SHIPPING_ZONE-v1 | ✓ | — (pure sales move) | **none** |
| SIZE_FIT-v1 | ✗ | — (pure sales move) | **none** |
| WARRANTY-v1 | ✓ | — (pure sales move) | **none** |

## PASS — zero product-specific values in cached templates

Every template encodes a reusable sales move (reassure, defer specifics to verified sources, ask the closing question). The same cache transfers to a new catalog without regeneration; product facts enter only through render-time slots.