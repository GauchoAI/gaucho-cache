#!/usr/bin/env python3
"""Prove cache values are sales intelligence, not product data.

The combinatorial space we cache is (stage × intent × sales-move) — the
funnel knowledge. Product-specific values (names, SKUs, prices, sizes,
stock numbers) must NEVER be baked into a cached template: they arrive
at render time through placeholders resolved from deterministic sources
(catalog DB, WooCommerce), or the template asks for them.

Checks every slice template body for:
- currency/price literals ($, ARS, AR$, digit groups that look like prices)
- percentage discounts
- concrete day/week delivery promises
- SKU-like tokens
- placeholder inventory (what slots each template declares/uses)

Merchant-level identity (store name, carrier, registry URL) is allowed —
that's the brand voice layer, deliberately merchant-coupled (agentic-crm
merchants/CLAUDE.md), orthogonal to product-coupling.

Writes reports/product-agnostic-check.md.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gaucho_cache.contracts import (default_contracts_dir, load_contracts,
                                    load_intent_specs)

REPO = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = default_contracts_dir(REPO)
INTENTS_YAML = REPO / "data" / "intents_slice.yaml"
REPORT_OUT = REPO / "reports" / "product-agnostic-check.md"

PATTERNS = {
    "price literal": re.compile(r"(\$|ARS|AR\$)\s?\d|(?<![\w/.])\d{1,3}([.,]\d{3})+(?![\w/])"),
    "percent discount": re.compile(r"\d+\s?%"),
    "concrete delivery promise": re.compile(
        r"\b\d+\s*(días?|semanas?|horas?|hs)\b", re.IGNORECASE),
    "concrete warranty duration": re.compile(
        r"\b\d+\s*(años?|meses?)\b", re.IGNORECASE),
    "SKU-like token": re.compile(r"\b[A-Z]{2,}-?\d{2,}\b"),
}
PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}|\{(\w+)\}")


def main() -> None:
    contracts = load_contracts(CONTRACTS_DIR)
    slice_intents = {s.intent for s in load_intent_specs(INTENTS_YAML)}

    violations: list[tuple[str, str, str]] = []
    lines = ["# Product-agnosticism check — cached values are sales moves\n",
             "| Template | audited | placeholders | product-specific literals |",
             "|---|---|---|---|"]
    for intent in sorted(slice_intents):
        c = contracts[intent]
        found = []
        for label, rx in PATTERNS.items():
            for m in rx.finditer(c.body):
                found.append(f"{label}: `{m.group(0)}`")
                violations.append((intent, label, m.group(0)))
        ph = [a or b for a, b in PLACEHOLDER.findall(c.body)]
        ph_decl = list(c.required_placeholders)
        lines.append(
            f"| {c.template_id} | {'✓' if c.audited else '✗'} "
            f"| {', '.join(ph or ph_decl) or '— (pure sales move)'} "
            f"| {'; '.join(found) or '**none**'} |")

    lines.append("")
    if violations:
        lines.append(f"## ⚠ FAIL — {len(violations)} product-specific "
                     "literals baked into templates\n")
        lines.append("These values must move to render-time placeholders "
                     "fed by the catalog/policy DB.")
    else:
        lines.append("## PASS — zero product-specific values in cached templates\n")
        lines.append(
            "Every template encodes a reusable sales move (reassure, defer "
            "specifics to verified sources, ask the closing question). The "
            "same cache transfers to a new catalog without regeneration; "
            "product facts enter only through render-time slots.")

    REPORT_OUT.parent.mkdir(exist_ok=True)
    REPORT_OUT.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    sys.exit(1 if violations else 0)


if __name__ == "__main__":
    main()
