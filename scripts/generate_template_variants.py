#!/usr/bin/env python3
"""Template variant rotation: kill the verbatim-template tell.

The Turing test exposed it: rubric non-inferior, safety perfect, but the
judge identified the canned reply 78.5% of the time — the SAME verbatim
text serves every turn. Fix: per template, generate paraphrase variants
that preserve every factual claim and the closing move, vary phrasing/
length/rhythm, then SAFETY-GATE each variant against the policy book
(a variant that adds or drops a fact is discarded). Serving rotates.

Variants are derived merchant copy: production serving keeps them
behind the same human-audit queue as the base templates. For the
benchmark they carry the base template's audit status explicitly.

Writes data/template_variants.json: {category: [base, v1, v2, ...]}.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gaucho_cache import spend
from gaucho_cache.cerebras import BatchClient
from gaucho_cache.contracts import default_contracts_dir, load_contracts

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "data" / "template_variants.json"
N_VARIANTS = 6

GEN_SYSTEM = ("You rewrite WhatsApp replies for an Argentine mattress "
              "store, preserving meaning exactly. Output ONLY a JSON "
              "array of strings.")

GEN_PROMPT = """Base reply (approved merchant copy, rioplatense voseo):
"{body}"

Write {n} paraphrase variants that:
- preserve EVERY factual claim exactly (no new facts, none dropped — same guarantees, same processes, same links if any)
- keep a closing question / next step (may rephrase it)
- vary sentence structure, openers, length (some shorter), and rhythm so no two feel like the same canned text
- keep the same warm rioplatense voseo voice, WhatsApp register

Output: JSON array of {n} strings."""

CHECK_SYSTEM = ("You audit paraphrases of approved merchant copy. "
                "Output ONLY JSON.")

CHECK_PROMPT = """Approved base reply:
"{body}"

Candidate paraphrases:
{numbered}

For each candidate: "ok" if it preserves every factual claim of the base (no additions, no omissions of guarantees/processes/links) and keeps a closing move; otherwise "reject" with the reason.

Output: JSON array of {{"i": <n>, "verdict": "ok"|"reject", "reason": "..."}}"""


async def main() -> None:
    contracts = load_contracts(default_contracts_dir(REPO),
                               REPO / "data" / "contract_extensions.yaml")
    client = BatchClient("template_variants")

    async def one(category: str, body: str) -> tuple[str, list[str]]:
        variants = await client.chat_json(
            GEN_SYSTEM, GEN_PROMPT.format(body=body, n=N_VARIANTS),
            temperature=0.9)
        variants = [str(v) for v in variants][:N_VARIANTS]
        numbered = "\n".join(f'{i}. "{v}"' for i, v in enumerate(variants))
        verdicts = await client.chat_json(
            CHECK_SYSTEM, CHECK_PROMPT.format(body=body, numbered=numbered),
            temperature=0.0)
        ok = {int(v["i"]) for v in verdicts
              if isinstance(v, dict) and v.get("verdict") == "ok"}
        kept = [variants[i] for i in sorted(ok) if i < len(variants)]
        return category, kept

    results = await asyncio.gather(
        *(one(c.category, c.body) for c in contracts.values()))
    out = {}
    for category, kept in results:
        base = contracts[category].body
        out[category] = [base] + kept
        print(f"{category:28s} base + {len(kept)} safety-gated variants")
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(f"\n✓ wrote {OUT}; ledger ${spend.spent():.2f}")


if __name__ == "__main__":
    asyncio.run(main())
