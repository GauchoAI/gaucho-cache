"""Class-B serving: template + deterministic slot-fill (PLAN §cacheability).

Class A serves a static template. Class B fills an audited template with
slots resolved by DETERMINISTIC computation — catalog lookups and payment
arithmetic, zero LLM. This is how the cache follows the funnel past the
greeting: recommendations, prices and cuotas are lookups, not generation.

Domain wisdom (mirrors agentic-crm laferia mattress scoring):
  posture → firmness preference: de costado favors blando/medio (pressure
  relief), boca abajo favors firme (lumbar), boca arriba favors medio/firme.

The catalog is mock (data/catalog.json, agentic-crm product shape); a real
deployment swaps the file, the contract here stays identical.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

_CATALOG = None
_LADDER = None


def catalog() -> dict:
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = json.loads((REPO / "data" / "catalog.json").read_text())
    return _CATALOG


def ladder() -> list[dict]:
    global _LADDER
    if _LADDER is None:
        _LADDER = json.loads(
            (REPO / "data" / "payment_ladder.json").read_text())["methods"]
    return _LADDER


# ---- slot extraction (deterministic, shared shapes with classifier) -------
SIZE_MAP = [
    (re.compile(r"\b1\s*plaza\s*y\s*media\b|\buna\s*plaza\s*y\s*media\b|\b1[,.]5\s*plazas?\b", re.I), "1 plaza y media"),
    (re.compile(r"\b(2|dos)\s*plazas?\b|\b140\s*x\s*190\b", re.I), "2 plazas"),
    (re.compile(r"\b(1|una)\s*plaza\b|\b90\s*x\s*190\b", re.I), "1 plaza"),
    (re.compile(r"\bqueen\b|\b160\s*x\s*200\b", re.I), "queen"),
    (re.compile(r"\bking\b|\b180\s*x\s*200\b|\b200\s*x\s*200\b", re.I), "king"),
]
POSTURE_FIRMNESS = [
    (re.compile(r"\bde\s+costado\b|\bde\s+lado\b|\bfetal\b", re.I), ("blando", "medio")),
    (re.compile(r"\bboca\s+abajo\b", re.I), ("firme", "medio firme")),
    (re.compile(r"\bboca\s+arriba\b|\bde\s+espaldas?\b", re.I), ("medio", "firme")),
]
FIRMNESS_RX = [
    (re.compile(r"\bextra\s*firme\b|\bbien\s+firme\b|\bdur[oa]\b", re.I), ("firme",)),
    (re.compile(r"\bfirme\b", re.I), ("firme", "medio firme")),
    (re.compile(r"\bbland[oa]\b|\bsuave\b|\bsoft\b", re.I), ("blando",)),
    (re.compile(r"\bmedi[oa]\b|\bintermedia?\b", re.I), ("medio", "medio firme")),
]


def extract_slots(text: str) -> dict:
    slots: dict = {}
    for rx, size in SIZE_MAP:
        if rx.search(text):
            slots["size"] = size
            break
    for rx, prefs in FIRMNESS_RX:        # explicit firmness wins
        if rx.search(text):
            slots["firmness_pref"] = prefs
            break
    if "firmness_pref" not in slots:     # else derive from posture
        for rx, prefs in POSTURE_FIRMNESS:
            if rx.search(text):
                slots["firmness_pref"] = prefs
                break
    return slots


# ---- deterministic pricing -------------------------------------------------
def _ars(n: float) -> str:
    return "$" + f"{int(round(n)):,}".replace(",", ".")


def best_offer(price: float) -> tuple[str, float]:
    m = min(ladder(), key=lambda m: m["multiplier"])
    return m["label"], price * m["multiplier"]


def payment_lines(price: float) -> list[str]:
    out = []
    for m in ladder():
        total = price * m["multiplier"]
        if m["cuotas"] > 1:
            out.append(f"• {m['label']}: {m['cuotas']}× {_ars(total / m['cuotas'])} "
                       f"(total {_ars(total)})")
        else:
            out.append(f"• {m['label']}: {_ars(total)}")
    return out


# ---- class-B renderers -----------------------------------------------------
def pick_products(size: str | None, firmness_pref: tuple[str, ...] | None,
                  k: int = 2) -> list[dict]:
    """Deterministic ranking: size match is a hard filter when given;
    firmness preference orders; on_sale breaks ties."""
    items = [p for p in catalog()["products"] if p["stock_status"] == "instock"]
    if size:
        items = [p for p in items if p["size"] == size] or items
    def rank(p):
        f = 0
        if firmness_pref:
            f = (0 if p["firmeza"] in firmness_pref
                 else 1 if any(fp in p["firmeza"] for fp in firmness_pref)
                 else 2)
        return (f, 0 if p["on_sale"] else 1, p["price"])
    return sorted(items, key=rank)[:k]


def render_recommendation(slots: dict) -> str | None:
    """The funnel's recommend step as a class-B serve. None when the
    slots aren't there — the ask-templates' job is to get them first."""
    size = slots.get("size")
    if not size:
        return None
    prods = pick_products(size, slots.get("firmness_pref"))
    if not prods:
        return None
    lines = []
    for p in prods:
        label, off = best_offer(p["price"])
        sale = " 🔥 en oferta" if p["on_sale"] else ""
        lines.append(
            f"• *{p['name']}* ({p['firmeza']}, {p['tecnologia']}, "
            f"{p['altura_cm']} cm){sale} — lista {_ars(p['price'])}, "
            f"con {label.lower()}: {_ars(off)}")
    return ("Estas son mis recomendaciones para tu cama "
            f"{size}: 🛏️\n" + "\n".join(lines) +
            "\n¿Te paso las opciones de pago de alguno, o querés ver otro estilo?")


def render_payment_options(slots: dict) -> str:
    """Cuotas/discount ladder for the recommended (or cheapest matching)
    product — pure arithmetic over the ladder file."""
    prods = pick_products(slots.get("size"), slots.get("firmness_pref"), k=1)
    p = prods[0]
    return (f"Para el *{p['name']}* (lista {_ars(p['price'])}) tenés: 💳\n"
            + "\n".join(payment_lines(p["price"]))
            + "\n¿Con cuál te queda cómodo? Apenas elijas te paso el link para cerrarlo.")


def render_close(slots: dict, method_key: str | None = None) -> str:
    """The close: confirm the chosen payment and hand the checkout link."""
    prods = pick_products(slots.get("size"), slots.get("firmness_pref"), k=1)
    p = prods[0]
    m = next((m for m in ladder() if m["method_key"] == method_key), None)
    if m is None:
        m = min(ladder(), key=lambda x: x["multiplier"])
    total = p["price"] * m["multiplier"]
    per = (f" ({m['cuotas']}× {_ars(total / m['cuotas'])})" if m["cuotas"] > 1 else "")
    return (f"¡Listo! 🎉 Te reservo el *{p['name']}* con {m['label'].lower()}: "
            f"{_ars(total)}{per}. Completá el pago acá y queda confirmado: "
            f"https://laferia.example/checkout/{p['sku']}?pago={m['method_key']} "
            "— cualquier cosa me escribís por acá.")


def detect_payment_choice(text: str) -> str | None:
    t = text.lower()
    if re.search(r"\befectivo\b|\bcontado\b|\bcash\b", t):
        return "efectivo"
    if re.search(r"\bd[eé]bito\b", t):
        return "debito"
    if re.search(r"\btransferencia\b|\btransfer\b", t):
        return "transferencia"
    if re.search(r"\b6\s*cuotas\b|\bseis\s*cuotas\b", t):
        return "cuotas_6"
    if re.search(r"\b3\s*cuotas\b|\btres\s*cuotas\b|\bcuotas\b", t):
        return "cuotas_3"
    return None
