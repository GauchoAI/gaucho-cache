"""The hybrid serving turn: classify → class-A template / class-B render / LLM.

This is the FSM-lite the production CRM runs at full size (ADR-0016): the
bot accumulates slots across turns, remembers what it already did
(recommended? offered payments?), and picks the funnel-advancing serve:

  slots known + funnel intent      → render_recommendation   (class B)
  payment chosen                   → render_close            (class B)
  recommended + ack/price interest → render_payment_options  (class B)
  otherwise                        → audited template         (class A)
  no confident route               → LLM lane (cents, never lies)

Everything class-B is catalog lookups + ladder arithmetic — zero LLM.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .render import (detect_payment_choice, detect_product_choice,
                     extract_slots, pick_products, product_by_id,
                     render_alternatives, render_close,
                     render_payment_options, render_recommendation)

import re

FUNNEL_INTENTS = {"answer_size_posture", "ask_recommendation",
                  "want_to_buy", "answer_for_whom"}
ACK_INTENTS = {"confirmation", "awaiting_reply"}
PAYMENT_ASK_RX = re.compile(
    r"opciones\s+de\s+pago|formas?\s+de\s+pago|c[oó]mo\s+(se\s+)?paga"
    r"|c[oó]mo\s+puedo\s+pagar|medios\s+de\s+pago", re.I)
NON_PRODUCT_RX = re.compile(
    r"env[ií]o|envios|garant[ií]a|devoluc|demora|cu[aá]nto\s+tarda|zona|"
    r"sucursal|local|mercado\s*pago", re.I)
ALTERNATIVES_RX = re.compile(
    r"otr[oa]s?\s+(estilo|opci[oó]n|opciones|modelo|alternativa)"
    r"|qu[eé]\s+(otro|m[aá]s)\s+(estilo\s+)?(hay|ten[eé]s)"
    r"|ver\s+otr[oa]s|mostrame\s+otr[oa]s|algo\s+m[aá]s\s+para\s+ver", re.I)


@dataclass
class BotState:
    slots: dict = field(default_factory=dict)
    recommended: bool = False
    offered_payments: bool = False
    closed: bool = False
    last_intent: str = "greet"
    salt: int = 0   # per-conversation phrasing rotation (anti-tell)
    shown: list = field(default_factory=list)   # product ids already pitched
    selected: int | None = None                 # customer-chosen product id


def serve_turn(clf, variants: dict, state: BotState, msg: str,
               rng: random.Random | None = None):
    """Returns (reply_text_or_None, lane, intent, reason).
    reply None → caller must take the LLM lane."""
    rng = rng or random
    state.slots.update(extract_slots(msg))
    pm = detect_payment_choice(msg)

    # The close is slot-gated, not similarity-gated: a stated payment
    # choice after a recommendation is deterministic evidence the
    # embedding doesn't need to confirm ("transferencia" routes poorly,
    # means exactly one thing here).
    if pm and state.recommended and len(msg.split()) <= 8:
        state.closed = True
        state.last_intent = "close"
        return (render_close(state.slots, pm, salt=state.salt,
                             product=product_by_id(state.selected)
                             if state.selected else None), "CACHE",
                "answer_payment_choice", "class_b_close")
    # "¿qué otro estilo hay?" — the recommendation outro's own invitation.
    # Pagination over the catalog, deterministic (the render asked it; the
    # render must hear it — Closure Principle, serving layer).
    if (state.recommended and ALTERNATIVES_RX.search(msg)
            and len(msg.split()) <= 10):
        alt = render_alternatives(state.slots, set(state.shown),
                                  salt=state.salt)
        for p in pick_products(state.slots.get("size"),
                               state.slots.get("firmness_pref"), k=2,
                               exclude=set(state.shown)):
            state.shown.append(p["id"])
        state.last_intent = "answer_size_posture"
        return alt, "CACHE", "ask_recommendation", "class_b_alternatives"
    # "el primero" / "la pampa" — product selection from what was shown.
    if state.recommended and not pm:
        pid = detect_product_choice(msg, state.shown)
        if pid is not None and len(msg.split()) <= 10:
            state.selected = pid
            state.offered_payments = True
            state.last_intent = "answer_payment_choice"
            return (render_payment_options(state.slots, salt=state.salt,
                                           product=product_by_id(pid)),
                    "CACHE", "answer_payment_choice", "class_b_select")
    # Same doctrine for the payment-options ASK: "pasame las opciones de
    # pago" after a recommendation is a ladder lookup, not a similarity call.
    if (state.recommended and not pm
            and PAYMENT_ASK_RX.search(msg) and len(msg.split()) <= 10):
        state.offered_payments = True
        state.last_intent = "answer_payment_choice"
        return (render_payment_options(state.slots, salt=state.salt,
                                       product=product_by_id(state.selected)
                                       if state.selected else None), "CACHE",
                "answer_payment_choice", "class_b_payments")

    # Slot-gated recommendation: a message carrying a size slot IS the
    # answer to the sizing question, whatever its embedding score
    # ("seria ehm, 1 plaza." scored 0.84 and fell silent — the slot was
    # right there). Deny-listed when a non-product concern rides along.
    fresh = extract_slots(msg)
    if (fresh.get("size") and not state.closed
            and len(msg.split()) <= 12 and not NON_PRODUCT_RX.search(msg)):
        reco = render_recommendation(state.slots, salt=state.salt)
        if reco:
            state.recommended = True
            for p in pick_products(state.slots.get("size"),
                                   state.slots.get("firmness_pref"), k=2):
                if p["id"] not in state.shown:
                    state.shown.append(p["id"])
            state.last_intent = "answer_size_posture"
            return reco, "CACHE", "answer_size_posture", "class_b_recommend"

    d = clf.classify(msg[:200], stage="objection",
                     last_bot_intent=state.last_intent)
    if not d.serve_eligible:
        return None, "LLM", d.intent, d.reason or "miss"

    intent = d.intent
    if intent in FUNNEL_INTENTS and state.slots.get("size"):
        reco = render_recommendation(state.slots, salt=state.salt)
        if reco:
            state.recommended = True
            for p in pick_products(state.slots.get("size"),
                                   state.slots.get("firmness_pref"), k=2):
                state.shown.append(p["id"])
            state.last_intent = "answer_size_posture"
            return reco, "CACHE", intent, "class_b_recommend"
    if intent == "answer_payment_choice" and state.recommended:
        state.offered_payments = True
        state.last_intent = "answer_payment_choice"
        return (render_payment_options(state.slots, salt=state.salt,
                                       product=product_by_id(state.selected)
                                       if state.selected else None),
                "CACHE", intent, "class_b_payments")
    if intent in ACK_INTENTS and state.recommended and not state.offered_payments:
        # "dale" after a recommendation means: move toward the close.
        state.offered_payments = True
        state.last_intent = "answer_payment_choice"
        return (render_payment_options(state.slots, salt=state.salt,
                                       product=product_by_id(state.selected)
                                       if state.selected else None),
                "CACHE", intent, "class_b_payments")
    if intent == "price" and state.recommended:
        state.offered_payments = True
        state.last_intent = "answer_payment_choice"
        return (render_payment_options(state.slots, salt=state.salt,
                                       product=product_by_id(state.selected)
                                       if state.selected else None),
                "CACHE", intent, "class_b_payments")

    # Class A — audited template (rotation pool).
    pool = variants.get(intent) or []
    if not pool:
        return None, "LLM", intent, "no_pool"
    state.last_intent = intent
    return rng.choice(pool), "CACHE", intent, d.reason or "template"
