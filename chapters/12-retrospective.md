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
| Web demo's main path never passed `rawText` into `decide()` — the curated-exact lane was dead code for every typed message ("dale" at score 1.00 vetoed by the multi-intent guard) | the user, three messages into a real conversation | pass the text through; drive the fixed demo in a real browser before pushing |
| CLI loaded only merchant templates (`load_contracts`), so every global intent reported `no_template` and the curated lane never fired there either | tracing the same "dale" through the Python stack | CLI defaults to `load_all_contracts` — the same contract set every other predicate site uses |
| "perfecto", "genial", "bárbaro", "de una" — uncurated bare acks | same demo session | 12 new curated constitution rows + 11 new probe-gate rows |
| Closure proven on one sample leaked ~40% on the next (the audit regenerates answers each run) | re-running the closure audit after the fix | judge-in-the-loop closure: coverable unheard answers are ingested as positives (`register='closure'`); novel/compound replies are CORRECT LLM-lane falls, not failures |
| declination threshold 0.892 — strangled by thanks_goodbye hard negatives seeded before the social cluster existed (in-cluster = harmless by doctrine) | tracing why the closure loop wouldn't converge | retire 84 in-cluster social negatives; recalibration drops declination to 0.693, hit rate 12%→49%, confident-wrong still 0 |
| First closure campaign ingested label-only: "Sí, pasame a la gente, porfa" under confirmation = cheerful proceed-ack to someone demanding a human | reading the ingestion log | template-fit judge gates ingestion; re-audit dropped 116/329 rows as serving traps |
| Compound guard vetoed an exact corpus member (s=1.000) and 2-word fragments ("tiene garantia") | closure non-convergence + probe regression | corpus-exact bypass; two words can't carry two concerns |
| eval's margin leg and the browser's margin leg never got the social-cluster exemption the classifier had (drift №3 and №4 of the same predicate) | side-by-side read during the corpus-exact port | all three sites synced in one diff; parity is now part of the closure chapter's checklist |
| Elaborated single-concern answers ("duermo de costado… la cama seria una plaza") vetoed as compounds — want_to_buy ranked second, but it's the same funnel move | the user, one-shot №3 | funnel-advancing cluster {want_to_buy, answer_size_posture, answer_for_whom}: in-cluster crossings are redundant questions at worst, never lies |
| Judge-labeled ingestions the router files elsewhere became eval confident-wrongs the moment they landed ("Aguardo, tranqui" filed awaiting_reply, routed answer_for_whom) | the eval gate, twice in one campaign | router pre-check in insert_positives: a label the router strongly disputes stays in the LLM lane |
| Template copy enumerated two slots and silently dropped the rest; then the "fix" (inviting preferences) blew the closure distribution open | the fit judge, then the closure audit | neutral ack ("con todo lo que me contaste"); invitation reverted — every word a template asks with, it must be able to hear the answers to |

The `rawText` row is the most instructive of the second wave: the
curated-exact lane was tested where it was written (Python) and assumed
where it was rewritten (JS). Three predicate re-implementations now
exist — classifier, eval, browser — and every divergence between them
has eventually been found by exactly one person: the user, typing the
most ordinary message imaginable. Gates only protect what they cover;
the demo's send button is now part of the manual pre-push checklist,
and the browser conversation above is driven end-to-end before any
push that touches the demo.

## The pattern

Every failure above became either a predicate leg, a curation pass, a
ledger, a regression-gate row, or a process rule. None became a
hidden patch. That is the entire method: **the system is exactly as
good as the failures it has metabolized — and it keeps the receipts.**
