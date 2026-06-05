# Zero-spend proof

Method: `socket.socket.connect` is replaced with a raising stub for the entire process (before any import); all `*API_KEY*`/`*TOKEN*` env vars are deleted; `HF_HUB_OFFLINE=1`. Any attempt by any component to reach a network endpoint would crash the run.

| Metric | Value |
|---|---|
| Turns processed | 184 |
| Network connections attempted | **0** |
| API spend | **$0.00 (by construction)** |
| Serve-eligible (audited hits) | 78 (42%) |
| Latency p50 / p95 | 11.4 ms / 31.8 ms |
| Cold start (model load + first encode) | 4.0 s |

**PASS — the runtime path cannot spend money.**