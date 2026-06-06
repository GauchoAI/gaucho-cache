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

from .render import (detect_payment_choice, extract_slots,
                     render_close, render_payment_options,
                     render_recommendation)

import re

FUNNEL_INTENTS = {"answer_size_posture", "ask_recommendation",
                  "want_to_buy", "answer_for_whom"}
ACK_INTENTS = {"confirmation", "awaiting_reply"}
PAYMENT_ASK_RX = re.compile(
    r"opciones\s+de\s+pago|formas?\s+de\s+pago|c[oó]mo\s+(se\s+)?paga"
    r"|c[oó]mo\s+puedo\s+pagar|medios\s+de\s+pago", re.I)


@dataclass
class BotState:
    slots: dict = field(default_factory=dict)
    recommended: bool = False
    offered_payments: bool = False
    closed: bool = False
    last_intent: str = "greet"


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
        return (render_close(state.slots, pm), "CACHE",
                "answer_payment_choice", "class_b_close")
    # Same doctrine for the payment-options ASK: "pasame las opciones de
    # pago" after a recommendation is a ladder lookup, not a similarity call.
    if (state.recommended and not pm
            and PAYMENT_ASK_RX.search(msg) and len(msg.split()) <= 10):
        state.offered_payments = True
        state.last_intent = "answer_payment_choice"
        return (render_payment_options(state.slots), "CACHE",
                "answer_payment_choice", "class_b_payments")

    d = clf.classify(msg[:200], stage="objection",
                     last_bot_intent=state.last_intent)
    if not d.serve_eligible:
        return None, "LLM", d.intent, d.reason or "miss"

    intent = d.intent
    if intent in FUNNEL_INTENTS and state.slots.get("size"):
        reco = render_recommendation(state.slots)
        if reco:
            state.recommended = True
            state.last_intent = "answer_size_posture"
            return reco, "CACHE", intent, "class_b_recommend"
    if intent == "answer_payment_choice" and state.recommended:
        state.offered_payments = True
        state.last_intent = "answer_payment_choice"
        return (render_payment_options(state.slots), "CACHE", intent,
                "class_b_payments")
    if intent in ACK_INTENTS and state.recommended and not state.offered_payments:
        # "dale" after a recommendation means: move toward the close.
        state.offered_payments = True
        state.last_intent = "answer_payment_choice"
        return (render_payment_options(state.slots), "CACHE", intent,
                "class_b_payments")
    if intent == "price" and state.recommended:
        state.offered_payments = True
        state.last_intent = "answer_payment_choice"
        return (render_payment_options(state.slots), "CACHE", intent,
                "class_b_payments")

    # Class A — audited template (rotation pool).
    pool = variants.get(intent) or []
    if not pool:
        return None, "LLM", intent, "no_pool"
    state.last_intent = intent
    return rng.choice(pool), "CACHE", intent, d.reason or "template"
