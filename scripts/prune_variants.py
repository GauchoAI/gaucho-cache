#!/usr/bin/env python3
"""Prune the variant pool: only variants that judge PERFECT survive.

The first Turing-with-rotation run showed the generation-time check is
too lenient: rotated variants scored safety 0.95 and a wider rubric gap
than the base templates. This pass judges every variant standalone on
the absolute rubric (vs the policy book) and keeps only those with a
perfect 4/4 — the pool shrinks, the tell stays dead, quality returns.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gaucho_cache import spend
from gaucho_cache.cerebras import BatchClient
from gaucho_cache.contracts import default_contracts_dir, load_all_contracts, load_contracts

REPO = Path(__file__).resolve().parent.parent
VARIANTS = REPO / "data" / "template_variants.json"

SYSTEM = ("You are an adversarial auditor: your job is to REFUTE a "
          "paraphrase's fidelity to approved copy. Output ONLY JSON.")
PROMPT = """APPROVED BASE TEMPLATE ({category}):
"{base}"

Candidate paraphrase:
"{reply}"

Hunt for ANY deviation: added claims/promises (however small: "mejor", "siempre", "garantizado", a stronger guarantee, a new process step), dropped claims (a missing link, a missing deferral-to-human, a lost condition), scope changes (specific→general or vice versa), or a weaker/missing closing move.

If you find ANY deviation, or you are uncertain: verdict "reject". Only a faithful paraphrase earns "ok".

Output JSON: {{"verdict":"ok"|"reject","reason":"..."}}"""


async def main() -> None:
    contracts = load_all_contracts(REPO,
                               REPO / "data" / "contract_extensions.yaml")
    book = "\n\n".join(f"[{c.category}] {c.body}" for c in contracts.values())
    pools = json.loads(VARIANTS.read_text(encoding="utf-8"))
    client = BatchClient("variant_prune")

    N_REFUTERS = 3

    async def judge(category: str, idx: int, reply: str):
        base = pools[category][0]
        verdicts = await asyncio.gather(*(
            client.chat_json(
                SYSTEM, PROMPT.format(category=category, base=base,
                                      reply=reply),
                temperature=0.3)
            for _ in range(N_REFUTERS)))
        perfect = all(isinstance(v, dict) and v.get("verdict") == "ok"
                      for v in verdicts)
        return category, idx, perfect

    jobs = [(c, i, r) for c, pool in pools.items()
            for i, r in enumerate(pool) if i > 0]  # base never judged out
    results = await asyncio.gather(*(judge(c, i, r) for c, i, r in jobs))
    keep: dict[str, set[int]] = {}
    for category, idx, perfect in results:
        if perfect:
            keep.setdefault(category, set()).add(idx)

    pruned = {}
    for category, pool in pools.items():
        kept_idx = keep.get(category, set())
        kept_idx.add(0)  # the audited base template always stays
        pruned[category] = [pool[i] for i in sorted(kept_idx)]
        print(f"{category:28s} {len(pool)} → {len(pruned[category])}")
    VARIANTS.write_text(json.dumps(pruned, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    print(f"✓ pruned pool written; ledger ${spend.spent():.2f}")


if __name__ == "__main__":
    asyncio.run(main())
