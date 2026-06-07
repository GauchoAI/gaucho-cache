#!/usr/bin/env python3
"""Build the COCO service domain from REAL customer phrasings (train split).

Seeds each service intent with the real customer turns labelled for it
(reports/coco_labels.json), holding out 30% of conversations for honest
measurement. The index is real phrasings; the templates are the audited
service flows (gaucho_cache/service.py); serving is class-B over the
mock order DB. No synthetic positives — the customers wrote the training
set.

Split rule (shared with reality_coverage --holdout): conv_idx %10 < 3 =
TEST, the rest TRAIN. Deterministic, so build and measure never overlap.

Usage: uv run python scripts/build_service_domain.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from gaucho_cache.classifier import Embedder, StageIndex

LABELS = REPO / "reports" / "coco_labels.json"
PACK = REPO / "data" / "domains" / "cocoshoes-service"

# topic label → service intent. Topics with a real templated flow only;
# product_question/payment/purchase/wholesale/other forward by design.
TOPIC_INTENT = {
    "order_status": "order_status",
    "exchange_return": "exchange_return",
    "shipping_coordination": "shipping_coordination",
    "restock_availability": "restock_availability",
    "complaint_problem": "complaint_problem",
    "greeting": "greeting",
    "thanks_closing": "thanks_closing",
}
# NOTE: store_hours / payment_info are NOT embedding intents — they're
# lexically distinctive and served by regex (service.detect_fact_intent),
# because thin synthetic seeds for them polluted the routing of the real
# service intents (ch. 29). Distinctive-lexical → regex; the rest → embedding.


def is_test(conv: int) -> bool:
    return conv % 10 < 3


async def densify(by_intent: dict[str, list[str]], per_intent: int):
    """Thicken each intent's neighbourhood with paraphrases of the REAL
    seeds (the medical 48.5%→95% move, on real customer phrasings). The
    model sees real examples and writes more in the same intent/register."""
    import sys as _s
    _s.path.insert(0, str(REPO))
    from gaucho_cache.cerebras import BatchClient
    client = BatchClient("service_density")
    GEN = ("You write realistic WhatsApp messages from Argentine shoe-store "
           "customers. Output ONLY a JSON array of strings.")

    async def gen(intent, seeds):
        ex = "\n".join(f"- {s}" for s in seeds[:12])
        prompt = (f"Real customer messages with intent '{intent}':\n{ex}\n\n"
                  f"Write {per_intent} MORE distinct messages with the same "
                  f"intent. Vary length (short fragments to chatty) and "
                  f"register (casual voseo, formal, typos/abbreviations). Some "
                  f"with an order number like #33421, some without.")
        # generate in batches of 20 so the JSON array never truncates at
        # max_tokens (the verbose service intents have long messages)
        out: list[str] = []
        while len(out) < per_intent:
            got = []
            for _ in range(3):
                try:
                    v = await client.chat_json(GEN, prompt + f"\n(write 20)",
                                               temperature=0.95, max_tokens=2000)
                    got = [str(x) for x in v][:20]
                    if got:
                        break
                except Exception:
                    continue
            if not got:
                break
            out.extend(got)
        return intent, out[:per_intent]
    out = {}
    for i, s in by_intent.items():       # sequential — avoids rate-limit
        _i, v = await gen(i, s)           # failures that thinned the cluster
        out[i] = v
    return out


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--densify", type=int, default=0,
                    help="paraphrases to generate per intent from real seeds")
    args = ap.parse_args()
    rows = json.loads(LABELS.read_text())
    train = [r for r in rows if not is_test(r["conv"])]
    by_intent: dict[str, list[str]] = defaultdict(list)
    for r in train:
        it = TOPIC_INTENT.get(r["topic"])
        if it and len(r["msg"].split()) >= 1:
            by_intent[it].append(r["msg"][:200])

    generated: dict[str, list[str]] = {}
    if args.densify:
        generated = asyncio.run(densify(by_intent, args.densify))

    intents, texts = [], []
    for it, msgs in by_intent.items():
        for m in dict.fromkeys(list(msgs) + generated.get(it, [])):
            intents.append(it)
            texts.append(m)
    print(f"{len(train)} train turns → {len(texts)} positives across "
          f"{len(by_intent)} service intents (real + {args.densify}/intent gen):")
    for it in sorted(by_intent):
        nreal = len(set(by_intent[it]))
        ngen = len(set(generated.get(it, [])))
        print(f"  {it:24s} {nreal} real + {ngen} gen")

    # REAL hard negatives: train turns whose topic has NO service flow
    # (other / payment / purchase / product / wholesale) must never serve a
    # service template. Attach each to its nearest positive's intent so the
    # negative-margin leg suppresses that neighbourhood — pre-certification
    # from real data, at zero runtime cost.
    neg_texts = list(dict.fromkeys(
        r["msg"][:200] for r in train
        if TOPIC_INTENT.get(r["topic"]) is None and len(r["msg"].split()) >= 2))

    emb = Embedder()
    vecs = emb.encode(texts)
    PACK.mkdir(parents=True, exist_ok=True)
    all_v, all_i, all_k, all_a = (list(vecs), list(intents),
                                  ["positive"] * len(intents),
                                  [""] * len(intents))
    if neg_texts:
        nv = emb.encode(neg_texts)
        pos_v = np.array(vecs)
        for j in range(len(neg_texts)):
            owner = intents[int((pos_v @ nv[j]).argmax())]
            all_v.append(nv[j]); all_i.append(owner)
            all_k.append("negative"); all_a.append("other")
        print(f"+ {len(neg_texts)} REAL hard negatives (non-service train turns)")
    StageIndex(np.array(all_v), np.array(all_i), np.array(all_k),
               np.array(all_a)).save(PACK / "index.npz")

    # thresholds: above what intents OUTSIDE the same safe-cluster reach
    # in. Sibling service intents don't inflate the threshold — confusing
    # them on the opener is harmless (they all ask for the order number).
    from gaucho_cache.service import SERVICE_CLUSTER
    posmask = np.array(all_k) == "positive"
    V = np.array(all_v)[posmask]
    I = np.array(all_i)[posmask]
    th = {}
    for it in sorted(set(intents)):
        m = I == it
        # foreign = different intent AND not a service-cluster sibling
        sib = SERVICE_CLUSTER if it in SERVICE_CLUSTER else set()
        o = np.array([(I[j] != it and I[j] not in sib) for j in range(len(I))])
        cross = float((V[o] @ V[m].T).max()) if o.any() else 0.6
        # cluster intents serve a shared ask → a lower floor is safe;
        # non-cluster (greeting/thanks) keep a firmer bar
        cap = 0.66 if it in SERVICE_CLUSTER else 0.82
        th[it] = {"threshold": min(cap, max(0.60, cross + 0.02)),
                  "margin": 0.04, "negative_margin": 0.03}
    (PACK / "thresholds.json").write_text(json.dumps(th, indent=1))
    # variants.json: the audited service flows (ask-form is the default
    # body; class-B fills the ref-form at serve time)
    from gaucho_cache.service import SERVICE
    variants = {it: [SERVICE[it]["ask"]] for it in SERVICE}
    variants["greeting"] = ["¡Hola! 😊 ¿En qué te puedo ayudar — un pedido, "
                            "un cambio, o algo más?"]
    variants["thanks_closing"] = ["¡Gracias a vos! 🤎 Cualquier cosa, escribime "
                                  "por acá."]
    (PACK / "variants.json").write_text(
        json.dumps(variants, ensure_ascii=False, indent=1))
    print(f"\n✓ service pack → {PACK} "
          f"({len(set(intents))} intents, held out 30% of convs for test)")


if __name__ == "__main__":
    main()
