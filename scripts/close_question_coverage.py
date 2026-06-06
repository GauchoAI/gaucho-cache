#!/usr/bin/env python3
"""Closure write-back loop: make the corpus hear its own questions' answers.

The audit (audit_question_coverage.py) samples fresh customer answers per
run, so 'closure' proven on one sample can leak on the next — exactly what
the 2026-06-06 demo session exposed ('dale' after the sizing question fell
to the LLM lane). This script runs the loop that converges it:

  round:
    1. generate N answers per questioning template (fresh sample, temp .9)
    2. classify through the full serving stack
    3. unheard answers → Cerebras judge with boundary-aware definitions
       and the bot question as context:
         - coverable intent  → REAL closure failure → insert as positive
                               (register='closure', judged_intent set)
         - other / ambiguous → correct LLM-lane fall (novel concern or
                               compound — the probe table demands these
                               miss; they are NOT closure failures)
    4. rebuild index + recalibrate thresholds
  stop when a fresh round yields 0 coverable-unheard (or MAX_ROUNDS).

Usage: CEREBRAS_API_KEY=... uv run python scripts/close_question_coverage.py
"""
from __future__ import annotations

import asyncio
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from arbitrate_ambiguity import BOUNDARIES  # single source of intent truth
from gaucho_cache import spend
from gaucho_cache.cerebras import BatchClient
from gaucho_cache.classifier import Classifier, StageIndex, load_thresholds
from gaucho_cache.contracts import load_all_contracts

DB_PATH = REPO / "data" / "slice.sqlite"
import os
N_ANSWERS = int(os.environ.get("GAUCHO_CLOSURE_N", "14"))
MAX_ROUNDS = int(os.environ.get("GAUCHO_CLOSURE_ROUNDS", "12"))
DRY_COVERABLE = 2   # a round this dry counts toward convergence
DRY_ROUNDS = 2      # consecutive dry rounds = closed against the distribution
STAGE = "objection"

# Per-round persona hints: each round samples a different slice of the
# answer distribution (the audit's stochasticity, made deliberate).
ROUND_FLAVORS = [
    "mix: direct answers, casual, with typos, one-word, with extra detail",
    "mix: chatty replies with side comments, voice-note style run-ons, lowercase no punctuation",
    "mix: terse replies, abbreviations (q, xq, tmb), numbers written as digits",
    "mix: polite formal usted replies, and replies that add a preference the bot didn't ask about",
    "mix: replies that answer then immediately ask to keep moving, and hesitant replies",
]

JUDGE_SYS = (
    "You are a strict data curator for a mattress-store WhatsApp bot. "
    "You will see the bot's question and a customer's DIRECT REPLY to it. "
    "Assign the reply to exactly one intent. Output ONLY a JSON object "
    '{"intent": "<name>"}.'
)

JUDGE_RULES = """Intent definitions:
%s

Reply-context rules (these messages are ANSWERS to the bot question shown):
- A reply stating sleep position, bed size, OR product preferences the bot's
  sizing question invites (firmness, material, weight, temperature) →
  answer_size_posture. A DOUBT about firmness suiting them → firmness_doubt.
- A reply agreeing to proceed / accepting the bot's offer → confirmation.
- A reply accepting a HUMAN HANDOFF the bot offered (pasame, derivame,
  asesor, operador, una persona) → bot_skepticism (the handoff template
  is the right reply, not a generic proceed-ack).
- A reply declining or postponing → declination.
- A reply saying who the mattress is for → answer_for_whom.
- A reply choosing a payment option → answer_payment_choice.
- A reply that asks a NEW specific question the definitions don't cover
  (specific model/color/stock/catalog/feature) → other. The LLM lane exists
  for these; do NOT force-fit them.
- A reply that agrees or declines BUT attaches a novel condition or
  request the templates can't honor ("sí, pero que hable inglés",
  "dale, pero rápido", "no, mejor mandame el catálogo por mail") →
  other. Serving a generic ack would ignore the condition.
- A reply carrying TWO distinct concerns → ambiguous.""" % BOUNDARIES

FIT_SYS = ("You audit a WhatsApp bot's CACHED reply for fitness. "
           'Output ONLY JSON {"verdict": "ok"|"reject", "reason": "..."}.')

FIT_PROMPT = """The customer just sent this reply to the bot:
"{answer}"
(it was an answer to the bot's question: "{question}")

The cache proposes serving this exact approved template:
"{template}"

Verdict "ok" ONLY if the template is a correct and COMPLETE response —
it must not ignore any request, condition or question the customer's
message carries. If the customer asked for something the template
doesn't address (a human agent, a language, a channel, a speed, a
specific product/detail), verdict "reject": the live LLM should answer
instead."""


async def judge_coverable(client: BatchClient, contracts, question: str,
                          answer: str) -> str | None:
    """Two-step verdict: intent label, then template-fit. Returns the
    intent to ingest under, or None when the LLM lane is the right home."""
    v = await client.chat_json(
        JUDGE_SYS,
        f'Bot question:\n"{question}"\n\nCustomer reply:\n"{answer}"\n\n'
        f"{JUDGE_RULES}", temperature=0.0)
    intent = str(v.get("intent", "ambiguous")).strip()
    c = contracts.get(intent)
    if intent in ("other", "ambiguous") or c is None:
        return None
    fit = await client.chat_json(
        FIT_SYS, FIT_PROMPT.format(answer=answer, question=question,
                                   template=c.body), temperature=0.0)
    if isinstance(fit, dict) and fit.get("verdict") == "ok":
        return intent
    return None


def serving_stack() -> Classifier:
    contracts = load_all_contracts(REPO, REPO / "data/contract_extensions.yaml")
    return Classifier(StageIndex.load(REPO / "index/slice-v1.npz"), contracts,
                      load_thresholds(REPO / "index/thresholds.json"))


def questioned_templates() -> dict[str, str]:
    contracts = load_all_contracts(REPO, REPO / "data/contract_extensions.yaml")
    return {c.category: c.body for c in contracts.values()
            if "?" in c.body.split(".")[-1] or c.body.rstrip().endswith("?")}


def is_heard(d) -> bool:
    """Same predicate the audit uses for the no-judge fast path."""
    if d.serve_eligible or d.decision == "hit":
        return True
    if d.reason in ("multi_intent", "ambiguous_margin"):
        return True
    return False


def insert_positives(rows: list[tuple[str, str]]) -> int:
    """rows: (intent, text). register='closure' marks audit-judged answers."""
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    n = 0
    for intent, text in rows:
        dup = cur.execute(
            "SELECT 1 FROM variants WHERE stage=? AND intent=? AND kind='positive' "
            "AND lower(text)=lower(?) AND dropped=0", (STAGE, intent, text)).fetchone()
        if dup:
            continue
        nxt = cur.execute(
            "SELECT COALESCE(MAX(variant_index),0)+1 FROM variants "
            "WHERE stage=? AND intent=? AND kind='positive' AND register='closure'",
            (STAGE, intent)).fetchone()[0]
        cur.execute(
            "INSERT INTO variants (stage,intent,kind,register,variant_index,text,judged_intent) "
            "VALUES (?,?, 'positive','closure',?,?,?)",
            (STAGE, intent, nxt, text, intent))
        n += 1
    con.commit()
    con.close()
    return n


def rebuild() -> None:
    for script in ("build_index.py", "eval_slice.py"):
        r = subprocess.run([sys.executable, str(REPO / "scripts" / script)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stdout[-2000:], r.stderr[-2000:])
            raise SystemExit(f"{script} failed during closure rebuild")


async def run_round(client: BatchClient, flavor: str) -> tuple[int, int, int]:
    """Returns (n_answers, n_coverable_unheard, n_llm_lane_ok)."""
    clf = serving_stack()
    questioned = questioned_templates()

    async def answers_for(cat: str, body: str):
        q = await client.chat_json(
            "You write realistic short WhatsApp replies from Argentine "
            "customers. Output ONLY a JSON array of strings.",
            f'The mattress-store bot just said:\n"{body}"\n\nWrite '
            f"{N_ANSWERS} realistic SHORT customer replies that directly "
            f"answer the bot's question ({flavor}). No new unrelated questions.",
            temperature=0.9)
        return cat, body, [str(x) for x in q][:N_ANSWERS]

    batches = await asyncio.gather(*(answers_for(c, b) for c, b in questioned.items()))

    unheard: list[tuple[str, str]] = []   # (bot_question, answer)
    total = 0
    for _cat, body, answers in batches:
        for a in answers:
            total += 1
            d = clf.classify(a, stage=STAGE)
            if not is_heard(d):
                unheard.append((body, a))

    if not unheard:
        return total, 0, 0

    contracts = load_all_contracts(REPO, REPO / "data/contract_extensions.yaml")
    verdicts = await asyncio.gather(
        *(judge_coverable(client, contracts, b, a) for b, a in unheard))
    coverable = [(i, a) for (_b, a), i in zip(unheard, verdicts) if i]
    llm_ok = len(verdicts) - len(coverable)

    n_new = insert_positives(coverable)
    for i, a in coverable[:8]:
        print(f"    closing: {a!r} → {i}")
    print(f"  round: {total} answers | {len(unheard)} unheard | "
          f"{len(coverable)} coverable (ingested {n_new} new) | "
          f"{llm_ok} legitimately LLM-lane")
    if n_new:
        rebuild()
    return total, len(coverable), llm_ok


async def main() -> None:
    """Loop-until-dry: the answer distribution is generative (fresh sample
    every round), so closure is a rate, not a checkbox. Convergence =
    DRY_ROUNDS consecutive fresh samples with ≤DRY_COVERABLE coverable
    leaks — and even those leaks are ingested (the ratchet only tightens)."""
    client = BatchClient("question_closure")
    dry = 0
    for rnd in range(MAX_ROUNDS):
        flavor = ROUND_FLAVORS[rnd % len(ROUND_FLAVORS)]
        print(f"— round {rnd + 1}/{MAX_ROUNDS} [{flavor[:48]}…]")
        total, coverable, _ = await run_round(client, flavor)
        dry_bound = max(DRY_COVERABLE, int(0.02 * total))  # the audit's 2%
        dry = dry + 1 if coverable <= dry_bound else 0
        if dry >= DRY_ROUNDS:
            print(f"\n✓ CLOSED against the distribution: {DRY_ROUNDS} "
                  f"consecutive fresh samples ≤{DRY_COVERABLE}/{total} "
                  f"coverable; ledger ${spend.spent():.2f}")
            return
    print(f"\n✗ still leaking after {MAX_ROUNDS} rounds; ledger ${spend.spent():.2f}")
    sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
