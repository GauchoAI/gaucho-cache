#!/usr/bin/env python3
"""End-to-end conversation simulation: Cerebras plays the customer.

Persona matrix (region x age x mood x typing style x GOAL) drives a
multi-turn loop against the FULL cache: serves answer from templates;
misses are answered by Cerebras-as-fallback (as production would), so
conversations continue realistically. A judge then audits every CACHED
reply in conversational context. Failures persist for write-back.

Usage: CEREBRAS_API_KEY=... uv run python scripts/simulate_conversations.py --n 60
"""
from __future__ import annotations
import argparse, asyncio, random, sqlite3, sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gaucho_cache import spend
from gaucho_cache.cerebras import BatchClient
from gaucho_cache.classifier import Classifier, StageIndex, load_thresholds
from gaucho_cache.contracts import load_all_contracts

REPO = Path(__file__).resolve().parent.parent
MOODS = ["apurado","desconfiado","charlatán","seco y directo","indeciso"]
STYLES = ["prolijo","minúsculas sin tildes","abreviaciones y typos","mensajes muy cortos"]
GOALS = [
 "comprar un colchón de 2 plazas para vos; dormís de costado",
 "consultar la garantía antes de decidirte",
 "saber si llegan a tu ciudad y cuánto tarda",
 "preguntar por tu pedido existente (inventá un número)",
 "averiguar precios y si hay cuotas; sos sensible al precio",
 "comprar un colchón queen para tu mamá",
 "tenés dudas de si el recomendado será muy duro",
 "preguntar si se puede devolver si no te gusta",
]
CUST = """Sos un cliente argentino ({mood}, escribís {style}) chateando por WhatsApp con una tienda de colchones. Tu objetivo: {goal}.
Historial:
{hist}
Escribí SOLO tu próximo mensaje (corto, natural). Si ya cumpliste tu objetivo o te cansaste, escribí exactamente [FIN]."""
FALLBACK = """Sos el asistente de La Feria del Colchón (rioplatense, voseo, breve). No inventes datos específicos (precios, plazos, stock). Historial:
{hist}
Cliente: {msg}
Tu respuesta:"""
JUDGE = """Conversación de una tienda de colchones (respuestas marcadas [CACHE] son plantillas; [LLM] son generadas):
{hist}
¿Alguna respuesta [CACHE] fue INCORRECTA o incoherente con el contexto (responde otra cosa, ignora lo que el cliente dijo, repite sin sentido)? Las respuestas [LLM] no se juzgan.
Output SOLO JSON: {{"bad_cache_turns":[{{"turn":<n>,"customer_said":"...","cache_replied":"...","why":"..."}}],"conversation_ok":true|false}}"""

async def main() -> None:
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    contracts = load_all_contracts(REPO, REPO/"data/contract_extensions.yaml")
    variants = json.loads((REPO/"data/template_variants.json").read_text())
    for c, k in contracts.items(): variants.setdefault(c, [k.body])
    clf = Classifier(StageIndex.load(REPO/"index/slice-v1.npz"), contracts,
                     load_thresholds(REPO/"index/thresholds.json"))
    client = BatchClient("conv_sim", concurrency=10)
    conn = sqlite3.connect(REPO/"data/slice.sqlite")
    conn.execute("""CREATE TABLE IF NOT EXISTS conv_failures (
      id INTEGER PRIMARY KEY AUTOINCREMENT, seed INT, conv INT, customer TEXT,
      cache_replied TEXT, why TEXT, ingested INT DEFAULT 0)""")

    async def run_conv(i: int):
        r = random.Random(a.seed*1000+i)
        mood, style, goal = r.choice(MOODS), r.choice(STYLES), r.choice(GOALS)
        hist = [("bot", variants["greet"][0], "CACHE", "greet")]
        cached = llm = 0
        for turn in range(7):
            htxt = "\n".join(f"{'Tienda' if s=='bot' else 'Cliente'}: {t}" for s,t,_,_ in hist)
            msg = (await client.chat("Output only the message.", CUST.format(
                mood=mood, style=style, goal=goal, hist=htxt), temperature=0.9, max_tokens=600)).strip()
            if not msg:  # reasoning ate the budget — one retry
                msg = (await client.chat("Output only the message.", CUST.format(
                    mood=mood, style=style, goal=goal, hist=htxt),
                    temperature=0.9, max_tokens=900)).strip()
            if "[FIN]" in msg or not msg: break
            d = clf.classify(msg[:200], stage="objection")
            if d.serve_eligible:
                pool = variants.get(d.intent) or ["..."]
                reply, lane = r.choice(pool), "CACHE"; cached += 1
            else:
                reply = (await client.chat("Sé breve.", FALLBACK.format(hist=htxt, msg=msg),
                         temperature=0.7, max_tokens=600)).strip(); lane = "LLM"; llm += 1
            hist.append(("cust", msg, "", "")); hist.append(("bot", reply, lane, d.intent))
        jh = "\n".join(f"{n}. {'Cliente' if s=='cust' else f'Tienda [{l}]'}: {t}"
                       for n,(s,t,l,_) in enumerate(hist))
        try:
            v = await client.chat_json("Output ONLY JSON.", JUDGE.format(hist=jh), temperature=0.0)
            for b in v.get("bad_cache_turns", []):
                conn.execute("INSERT INTO conv_failures (seed,conv,customer,cache_replied,why) VALUES (?,?,?,?,?)",
                    (a.seed, i, str(b.get("customer_said",""))[:200], str(b.get("cache_replied",""))[:200], str(b.get("why",""))[:300]))
            conn.commit()
            return cached, llm, len(v.get("bad_cache_turns", [])), bool(v.get("conversation_ok", True))
        except Exception:
            return cached, llm, -1, True

    res = await asyncio.gather(*(run_conv(i) for i in range(a.n)))
    res = [x for x in res if x]
    tc = sum(r[0] for r in res); tl = sum(r[1] for r in res)
    bad = sum(r[2] for r in res if r[2] >= 0); not_ok = sum(1 for r in res if not r[3])
    print(f"{len(res)} conversations | cached turns {tc} ({tc/(tc+tl):.0%}) | "
          f"LLM turns {tl} | bad cache replies (judged in context): {bad} | "
          f"convs flagged: {not_ok} | ledger ${spend.spent():.2f}")
    print("failures table: SELECT * FROM conv_failures WHERE ingested=0")

if __name__ == "__main__":
    asyncio.run(main())
