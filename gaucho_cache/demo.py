"""Demo: the cache deciding live, with zero API calls.

Two modes (both offline after the embedding model is cached):
- interactive: a REPL — type customer messages in Spanish, watch the
  decision pipeline (route → compound predicate → serve/miss) and the
  served template reply.
- scripted: a curated tour showing a clean hit, a slang/typo hit, the
  negative-margin block, a compound-message miss, an out-of-taxonomy
  miss, and the state-precondition gate.
"""

from __future__ import annotations

import time

from .classifier import Classifier
from .contracts import CacheDecision, MatchContract

BOLD, DIM, RESET = "\033[1m", "\033[2m", "\033[0m"
GREEN, YELLOW, RED, CYAN = "\033[32m", "\033[33m", "\033[31m", "\033[36m"

SCRIPTED_TOUR: list[tuple[str, str]] = [
    ("Clean hit — audited template serves at ~10ms, $0",
     "¿Hacen envíos a Córdoba capital?"),
    ("Slang + typos still route (the noise axis of the variant matrix)",
     "la garantia q onda?"),
    ("Boundary block — payment-method question must NOT serve the price template",
     "¿puedo pagar con Mercado Pago?"),
    ("Compound message — two concerns → miss → goes to the LLM fallback",
     "si no me gusta lo devuelvo? y cuanto tarda en llegar?"),
    ("Out of taxonomy — the cache knows what it doesn't know",
     "¿venden sommiers?"),
    ("State precondition — 'no hay stock' is a state claim; without known "
     "stock state the match contract blocks the serve",
     "se agotó! puedo reservar uno?"),
    ("Audit gate — routed perfectly, but the v2 template awaits human "
     "re-audit, so it stays shadow-only (PLAN §12)",
     "es muy caro para mi"),
    ("Bot skepticism — the honest audited template closes the tour",
     "sos un bot no? pasame con alguien"),
]


def _decision_lines(d: CacheDecision,
                    contracts: dict[str, MatchContract],
                    ms: float) -> list[str]:
    served = d.serve_eligible
    color = GREEN if served else (YELLOW if d.decision == "hit" else RED)
    verdict = ("SERVE" if served
               else f"HIT-NO-SERVE ({d.reason})" if d.decision == "hit"
               else f"MISS ({d.reason})")
    out = [
        f"  {color}{BOLD}{verdict}{RESET}  {DIM}{ms:.1f} ms, $0.00{RESET}",
        f"  intent={CYAN}{d.intent}{RESET} score={d.score} "
        f"margin={d.margin} neg_margin={d.negative_margin}"
        + (f" nearest_neg={d.nearest_negative}" if d.nearest_negative else ""),
    ]
    if served and d.intent in contracts:
        body = contracts[d.intent].body
        out.append(f"  {DIM}template {d.template_id}:{RESET}")
        out.append(f"  {GREEN}→ {body}{RESET}")
    elif d.decision == "hit":
        out.append(f"  {DIM}(routed correctly, but serving blocked — "
                   f"this turn falls back to the LLM){RESET}")
    else:
        out.append(f"  {DIM}(falls back to the LLM — a miss costs cents, "
                   f"a wrong answer costs trust){RESET}")
    return out


def run_scripted(clf: Classifier, contracts: dict[str, MatchContract]) -> None:
    print(f"{BOLD}Gaucho Caché — scripted tour{RESET}")
    print(f"{DIM}Every decision below is computed locally: embedding + "
          f"cosine + compound predicate. No API. No spend.{RESET}\n")
    clf.classify("hola", stage="objection")  # warm-up outside the timings
    for title, utterance in SCRIPTED_TOUR:
        print(f"{BOLD}■ {title}{RESET}")
        print(f"  {CYAN}customer:{RESET} {utterance}")
        t0 = time.perf_counter()
        d = clf.classify(utterance, stage="objection")
        ms = (time.perf_counter() - t0) * 1000
        print("\n".join(_decision_lines(d, contracts, ms)), end="\n\n")


def run_interactive(clf: Classifier,
                    contracts: dict[str, MatchContract]) -> None:
    print(f"{BOLD}Gaucho Caché — interactive demo{RESET}")
    print(f"{DIM}Type a customer message in Spanish (objection stage). "
          f"Empty line or Ctrl-D to exit. Try: precios, envíos, garantía, "
          f"devoluciones, '¿sos un bot?', typos welcome.{RESET}\n")
    clf.classify("hola", stage="objection")  # warm-up
    while True:
        try:
            text = input(f"{CYAN}customer>{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not text:
            break
        t0 = time.perf_counter()
        d = clf.classify(text, stage="objection")
        ms = (time.perf_counter() - t0) * 1000
        print("\n".join(_decision_lines(d, contracts, ms)), end="\n\n")
