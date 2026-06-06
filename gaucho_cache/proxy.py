"""The learning proxy: hook up ANY agent, watch the API calls die.

An OpenAI-compatible layer. Any agent that speaks chat-completions —
Cerebras, OpenAI, Codex, anything — points its base_url here and changes
nothing else. The proxy's lifecycle per domain:

  SHADOW       every call forwards to the provider; traffic is logged
               (last user turn + last bot turn + the provider's reply).
  DISTILL      (offline, scripts/distill_traffic.py) the existing
               machinery mines the logs: recurring user turns cluster
               into intents, the agent's own recurring answers become
               template candidates, judges audit, calibration runs.
  SHADOW-SERVE the cache decides every turn but the provider still
               answers; agreement between the would-be serve and the
               provider's actual reply accrues EVIDENCE per template.
  SERVE        evidence-gated templates answer directly ($0); misses
               still forward; every miss is future corpus. The ratchet
               only tightens — the hit-rate curve is the product.

This module is transport + decision + logging. It deliberately reuses
the serving stack unchanged: the same predicate, the same doctrine
(never lie; silence is a miss, not a guess).
"""
from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

SCHEMA = """
CREATE TABLE IF NOT EXISTS traffic (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    ts REAL NOT NULL,
    last_bot TEXT,
    user_msg TEXT NOT NULL,
    provider_reply TEXT,
    cache_intent TEXT,
    cache_reason TEXT,
    cache_would_serve TEXT,
    served_by TEXT NOT NULL,         -- 'provider' | 'cache'
    shadow_agreement REAL            -- fit score of would-serve vs reply
);
CREATE TABLE IF NOT EXISTS template_evidence (
    domain TEXT NOT NULL,
    intent TEXT NOT NULL,
    agreements INTEGER DEFAULT 0,
    disagreements INTEGER DEFAULT 0,
    promoted INTEGER DEFAULT 0,      -- 1 = allowed to serve live
    PRIMARY KEY (domain, intent)
);
"""

PROMOTE_MIN_AGREEMENTS = 4     # shadow agreements before a template serves
PROMOTE_MAX_DISAGREE_RATE = 0.2


@dataclass
class ProxyDecision:
    reply: str
    served_by: str          # 'cache' | 'provider'
    intent: str | None
    reason: str | None
    cost_usd: float


class LearningProxy:
    """One instance per (domain, provider). `classifier` may be None —
    that IS the bootstrap state: pure shadow, everything forwards."""

    def __init__(self, domain: str, forward_fn, db_path: Path | None = None,
                 classifier=None, variants: dict | None = None,
                 mode: str = "auto"):
        self.domain = domain
        self.forward = forward_fn      # async (messages) -> (text, cost)
        self.db = sqlite3.connect(db_path or REPO / "data" / "proxy_traffic.sqlite")
        self.db.executescript(SCHEMA)
        self.clf = classifier
        self.variants = variants or {}
        self.mode = mode               # 'shadow' | 'shadow_serve' | 'serve' | 'auto'

    # -- evidence ------------------------------------------------------------
    def _promoted(self, intent: str) -> bool:
        row = self.db.execute(
            "SELECT agreements, disagreements, promoted FROM template_evidence "
            "WHERE domain=? AND intent=?", (self.domain, intent)).fetchone()
        if not row:
            return False
        ag, dis, promoted = row
        if promoted:
            return True
        total = ag + dis
        if (ag >= PROMOTE_MIN_AGREEMENTS
                and (dis / total if total else 1) <= PROMOTE_MAX_DISAGREE_RATE):
            self.db.execute(
                "UPDATE template_evidence SET promoted=1 WHERE domain=? AND intent=?",
                (self.domain, intent))
            self.db.commit()
            return True
        return False

    def _record_evidence(self, intent: str, agreed: bool) -> None:
        self.db.execute(
            "INSERT INTO template_evidence (domain,intent,agreements,disagreements) "
            "VALUES (?,?,?,?) ON CONFLICT(domain,intent) DO UPDATE SET "
            "agreements=agreements+excluded.agreements, "
            "disagreements=disagreements+excluded.disagreements",
            (self.domain, intent, int(agreed), int(not agreed)))
        self.db.commit()

    # -- the turn -------------------------------------------------------------
    async def chat(self, messages: list[dict],
                   agreement_judge=None) -> ProxyDecision:
        """messages: OpenAI chat format. The proxy inspects the last user
        turn (and the last assistant turn as conversation state)."""
        user_msg = next((m["content"] for m in reversed(messages)
                         if m["role"] == "user"), "")
        last_bot = next((m["content"] for m in reversed(messages)
                         if m["role"] == "assistant"), None)

        would_serve, intent, reason = None, None, None
        if self.clf is not None and user_msg:
            d = self.clf.classify(user_msg[:200], stage=self.domain)
            intent, reason = d.intent, d.reason
            if d.serve_eligible:
                pool = self.variants.get(d.intent) or []
                if pool:
                    would_serve = pool[hash(user_msg) % len(pool)]

        # SERVE: evidence-gated cache answers; the provider stays silent.
        if (would_serve and self.mode in ("serve", "auto")
                and self._promoted(intent)):
            self._log(last_bot, user_msg, None, intent, reason,
                      would_serve, "cache", None)
            return ProxyDecision(would_serve, "cache", intent, reason, 0.0)

        # SHADOW / SHADOW-SERVE: forward, and if the cache had an opinion,
        # score the agreement so the template earns (or loses) evidence.
        reply, cost = await self.forward(messages)
        agreement = None
        if would_serve and agreement_judge is not None:
            try:
                agreement = await agreement_judge(user_msg, would_serve, reply)
                self._record_evidence(intent, agreement >= 0.5)
            except Exception:  # noqa: BLE001 — judging must never break serving
                pass
        self._log(last_bot, user_msg, reply, intent, reason,
                  would_serve, "provider", agreement)
        return ProxyDecision(reply, "provider", intent, reason, cost)

    def _log(self, last_bot, user_msg, reply, intent, reason,
             would_serve, served_by, agreement) -> None:
        self.db.execute(
            "INSERT INTO traffic (domain,ts,last_bot,user_msg,provider_reply,"
            "cache_intent,cache_reason,cache_would_serve,served_by,"
            "shadow_agreement) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (self.domain, time.time(), last_bot, user_msg, reply,
             intent, reason, would_serve, served_by, agreement))
        self.db.commit()

    # -- reporting -------------------------------------------------------------
    def hit_rate(self) -> tuple[int, int]:
        row = self.db.execute(
            "SELECT SUM(served_by='cache'), COUNT(*) FROM traffic WHERE domain=?",
            (self.domain,)).fetchone()
        return int(row[0] or 0), int(row[1] or 0)
