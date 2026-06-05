"""Gaucho Caché — semantic stage cache for FSM-funnel chatbots.

Stage-constrained semantic router plus deterministic renderer: classify
an inbound message into a finite (stage, intent) label space with a
local embedding model, and serve a templated answer when — and only
when — the compound hit predicate passes (PLAN.md §§10-13).
"""

__version__ = "0.1.0"
