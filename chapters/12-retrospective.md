# Retrospective: successes, failures, and what fixed them

This project's method was to let gates fail loudly and write down why.
This chapter is the ledger of both columns.

## Successes (each one measured, not claimed)

- **Four foundational proofs**: 95.7% routing / 0.00% confident-wrong;
  $0 runtime by socket-blocked construction (p50 ~11 ms); quality
  parity 0.972 = 0.972 with safety 1.00 vs the API's 0.91;
  product-agnostic templates 10/10.
- **Battle convergence**: six waves of independent traffic,
  5.25% → ~1.1% audited wrong-serves; novelty false-serves 0.04%.
- **Sales Turing test**: template identified at 47% — chance —
  after variant rotation; zero named safety violations.
- **A real conversation**: greet → concern → answer → thanks, 3–6 ms
  per turn, in any browser, from a single HTML file.
- **Real-data validation**: 59 real openers; every class handled —
  social served, order-status served (ask-the-slot), out-of-domain
  refused honestly.
- **Domain transfer**: a shoes cache from 58 real conversations —
  floor 25/59 for $0; full pipeline + shared social layer **44/59
  (75%)** for ~$0.60.

## Failures found, and their fixes (the more valuable column)

| Failure | Found by | Fix |
|---|---|---|
| Generator label noise ("¿Tienen garantía?" filed under brand_trust) | round-1 eval | judge every label (58 batched calls) |
| Cross-intent duplicates & compound positives | round-2 confident-wrongs | dedup + ambiguity arbitration; ambiguity = miss path |
| Lexical howlers ("cama cara" → size_fit) | round-3 | model bake-off on OUR failure modes, not leaderboards |
| Compounds served single templates (5.25%) | battle wave 1 | multi-intent leg + failure write-back as negatives |
| Battle negatives collapsing serve rate 12.4→3.5% | wave-2 re-eval | calibration excludes them; they block via negative-margin only |
| Verbatim-template tell (judge spots it 78.5%) | Turing v1 | variant rotation, adversarially pruned |
| One drifted variant ("soy el bot") | diagnostic logging | logged, traced, surgically removed |
| Judge flagged audited merchant facts as "invented" | quality v1 | give both arms and the judge the policy book |
| "Como va?" blocked as compound | user playing with the demo | length-aware multi guard; fragments need comparable 2nd intent |
| "is anyone there" in two intents | regression probe | taxonomy fix; 48 spec-artifact hybrids dropped |
| Arbitration deleting greetings it had no definitions for | probe regression | friendly-fire fix; 91 positives restored |
| Pushes silently failing (origin stale at commit 1) | clone test from GitHub | explicit refspec + fetch-verify after every push |
| A `git add -A` in the wrong repo published WIP to main | immediate output review | force-with-lease restore; `git -C` discipline memorized |
| **Demo shipped broken (shadowed `const m` killed the module)** | **the user clicking send** | rename + rule: re-verify in a real browser after EVERY JS edit, before every push |

The last row is the freshest and the most instructive: after a session
of verified shipping, one unverified patch — pushed on the strength of
an earlier verification — broke the only thing a visitor touches first.
Gates only protect what they cover; the demo's send button is now part
of the manual pre-push checklist, and should become an automated one.

## The pattern

Every failure above became either a predicate leg, a curation pass, a
ledger, a regression-gate row, or a process rule. None became a
hidden patch. That is the entire method: **the system is exactly as
good as the failures it has metabolized — and it keeps the receipts.**
