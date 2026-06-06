"""CLI: `gaucho-cache classify --stage objection "cuanto tarda en llegar?"`

Prints a CacheDecision as JSON (PLAN.md §11 contract).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .classifier import Classifier, StageIndex, load_thresholds
from .contracts import default_contracts_dir, load_all_contracts, load_contracts

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = REPO_ROOT / "index" / "slice-v1.npz"
DEFAULT_THRESHOLDS = REPO_ROOT / "index" / "thresholds.json"
DEFAULT_CONTRACTS = default_contracts_dir(REPO_ROOT)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gaucho-cache")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("classify", help="route one utterance")
    c.add_argument("text")
    c.add_argument("--stage", required=True)
    for p in (c, sub.add_parser("demo", help="interactive REPL demo"),
              sub.add_parser("tour", help="scripted showcase")):
        p.add_argument("--index", type=Path, default=DEFAULT_INDEX)
        p.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS)
        p.add_argument("--contracts", type=Path, default=DEFAULT_CONTRACTS)

    args = ap.parse_args(argv)

    if not args.index.exists():
        print(f"index not found: {args.index} (run scripts/build_index.py "
              f"or scripts/hf_sync.py pull)", file=sys.stderr)
        return 2

    extensions = REPO_ROOT / "data" / "contract_extensions.yaml"
    if args.contracts == DEFAULT_CONTRACTS:
        # Default run: merchant templates + the global conversational
        # intents (greet/confirmation/… in data/templates_globals) — same
        # contract set every other predicate site uses.
        contracts = load_all_contracts(REPO_ROOT, extensions)
    else:
        contracts = load_contracts(args.contracts, extensions)
    clf = Classifier(
        index=StageIndex.load(args.index),
        contracts=contracts,
        thresholds=load_thresholds(args.thresholds),
    )
    if args.cmd == "demo":
        from .demo import run_interactive
        run_interactive(clf, contracts)
        return 0
    if args.cmd == "tour":
        from .demo import run_scripted
        run_scripted(clf, contracts)
        return 0
    print(clf.classify(args.text, stage=args.stage).to_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
