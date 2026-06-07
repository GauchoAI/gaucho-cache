"""Service-graph serving: the post-sale subgraphs, class-B over an order DB.

Chapter 24 measured that the real e-commerce business is service, not
sales. This module serves the service flows the way the funnel served
sales: an audited template + DETERMINISTIC slot-fill. The slots
(<order_id>, <status>, <eta>, <tracking>) come from an order lookup, not
from generation — so an order-status reply is as un-inventable as a
price was (chapter 21).

Two move types per service intent:
  HAS-REF   the customer gave an order number → look it up, fill the
            template ("tu pedido #X está <status>, llega <eta>").
  NO-REF    no number yet → the reusable move is to ASK for it.

The order DB is mock (data/orders.json); a real deploy swaps the file,
the contract is identical.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_ORDERS = None

ORDER_RX = re.compile(r"#?\b(\d{5})\b")

# the service safe-cluster: every one of these answers a no-reference
# opener identically ("pasame tu número de pedido y te ayudo"), so a
# mis-route AMONG them on the opener is harmless — the same doctrine as
# the social/funnel clusters (chapters 13, 16). The has-reference turn,
# where the customer states their goal with the number, is where they
# branch.
# the REF cluster: the four intents that answer a no-reference opener with
# the SAME ask ("pasame tu número de pedido"). Confusing them is harmless
# because the served ask is identical. restock is NOT here (it asks for
# model+size, a different ask), so it must be routed confidently on its own.
SERVICE_CLUSTER = {"order_status", "exchange_return", "shipping_coordination",
                   "complaint_problem"}
UNIFIED_ASK = ("¡Claro, te ayudo! 😊 Pasame tu número de pedido (está en el "
               "mail de confirmación) y me decís qué necesitás — estado, "
               "cambio o envío — y lo resolvemos.")
# closers / waiting acks: not a fresh service request → forward, never
# trigger a new ask.
CLOSER_RX = re.compile(
    r"\b(lo|te|los|las) espero\b|cualquier cosa (te )?aviso|quedo a la espera|"
    r"te aviso|ya est[aá]|gracias|buenas noches|hasta luego|saludos\b", re.I)

# the REAL previous store message is ground-truth context: if the store
# just asked for an order number, the next customer turn is its answer —
# an unambiguous graph edge, not a guess.
PREV_ASKS_REF = re.compile(
    r"n[uú]mero de pedido|detall[aá]|pas[aá](me|nos)?.*(pedido|orden)|"
    r"cu[aá]l es tu pedido|qu[eé] pedido|orden de compra", re.I)


def prev_asked_for_ref(prev: str | None) -> bool:
    return bool(prev and PREV_ASKS_REF.search(prev))


def orders() -> dict:
    global _ORDERS
    if _ORDERS is None:
        p = REPO / "data" / "orders.json"
        _ORDERS = json.loads(p.read_text())["orders"] if p.exists() else {}
    return _ORDERS


def extract_order_id(text: str) -> str | None:
    m = ORDER_RX.search(text or "")
    return m.group(1) if m else None


def _fill(tmpl: str, o: dict) -> str:
    for k, v in o.items():
        tmpl = tmpl.replace(f"<{k}>", str(v))
    return tmpl


# audited service templates — has-ref (slotted) and no-ref (asks). A real
# merchant signs these in their domain spec; these are the COCO defaults.
SERVICE = {
    "order_status": {
        "ref": "¡Listo! 📦 Tu pedido #<order_id> está <status> y llega "
               "aprox. <eta>. Seguimiento <carrier>: <tracking>. "
               "¿Necesitás algo más?",
        "ask": "¡Claro! 😊 Pasame tu número de pedido (lo encontrás en el "
               "mail de confirmación) y te digo al toque en qué estado está.",
    },
    "exchange_return": {
        "ref": "¡Te ayudo con el cambio del pedido #<order_id>! 🔁 Decime el "
               "talle nuevo que querés y te genero la etiqueta de cambio sin "
               "cargo; coordinás el retiro con el cadete.",
        "ask": "¡Por supuesto! 🔁 Para gestionar el cambio pasame tu número de "
               "pedido y el talle nuevo que necesitás, y te genero la etiqueta.",
    },
    "shipping_coordination": {
        "ref": "¡Perfecto! 🚚 Para el pedido #<order_id> lo despachamos a la "
               "dirección del pedido; puede recibirlo cualquier persona en el "
               "domicilio. Si querés cambiar algo, decime.",
        "ask": "¡Dale! 🚚 Pasame tu número de pedido y coordinamos el envío — "
               "puede recibirlo un familiar o vecino, y si necesitás cambiar "
               "la dirección o la franja, lo vemos.",
    },
    "restock_availability": {
        "ref": "",
        "ask": "¡Gracias por avisarnos! 🙌 Decime el modelo y el talle que "
               "buscás y te anoto para avisarte apenas vuelva a entrar en "
               "stock.",
    },
    "complaint_problem": {
        "ref": "Lamento mucho lo que pasó con el pedido #<order_id> 🙏 Ya lo "
               "derivo al equipo para darte una solución; te respondemos por "
               "acá a la brevedad.",
        "ask": "Lamento mucho lo que pasó 🙏 Contame tu número de pedido y el "
               "detalle, y lo derivo al equipo para resolverlo cuanto antes.",
    },
}


# turns the cache must NEVER serve a service flow to: media placeholders
# (an image/audio the customer sent — no text to act on) and bare acks
# (a closing nicety, not a service request). Both forward.
MEDIA_RX = re.compile(r"message type can.?t be displayed|no.?t supported yet",
                      re.I)
BARE_ACK = {"oki", "ok", "oka", "okok", "dale", "listo", "joya", "buenísimo",
            "perfecto", "genial", "ah", "ahh", "aa", "si", "sí", "ya"}


NO_FLOW_RX = re.compile(
    r"devoluci[oó]n del dinero|reembols|me devuelv[ae]n? (el|la|mi)? ?(plata|"
    r"dinero|pago)|modificar (los )?datos|cambiar (la )?direcci[oó]n",
    re.I)


def serve_service(intent: str, text: str, *, continuation: bool = False
                  ) -> tuple[str, str] | None:
    """Returns (reply, reason) or None if this intent has no flow, or the
    turn must forward (media / no-flow concern / bare fresh ack)."""
    flow = SERVICE.get(intent)
    if not flow:
        return None
    t = (text or "").strip()
    if MEDIA_RX.search(t) or not t:
        return None                       # media/empty → forward
    if NO_FLOW_RX.search(t):
        return None                       # out-of-graph concern → forward
    oid = extract_order_id(text)
    if not oid and CLOSER_RX.search(t):
        return None                       # closer/waiting ack → forward (even
        #                                   mid-flow: "lo espero" ends the turn)
    if (not continuation and t.lower().strip(" .!¡?") in BARE_ACK
            and not oid):
        return None                       # bare FRESH ack → not a request
    # ref-cluster (the four sharing one ask): a no-reference turn gets the
    # UNIFIED ask, so an in-cluster mis-route serves the correct shared ask.
    if not oid and intent in SERVICE_CLUSTER:
        return UNIFIED_ASK, "service_ask_ref"
    if oid and flow.get("ref"):
        o = orders().get(oid)
        if o:
            return _fill(flow["ref"], o), "class_b_order_lookup"
        # number given but unknown → still acknowledge + ask to verify
        return (f"No encuentro el pedido #{oid} 🤔 ¿Me lo reconfirmás? "
                "A veces el número está en el asunto del mail de confirmación.",
                "class_b_order_notfound")
    return flow["ask"], "service_ask_ref"
