"""CLI: `gaucho-cache classify --stage objection "cuanto tarda en llegar?"`

Prints a CacheDecision as JSON (PLAN.md §11 contract).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .classifier import Classifier, StageIndex, load_thresholds
from .contracts import load_contracts

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDEX = REPO_ROOT / "index" / "slice-v1.npz"
DEFAULT_THRESHOLDS = REPO_ROOT / "index" / "thresholds.json"
DEFAULT_CONTRACTS = (
    REPO_ROOT.parent / "agentic-crm" / "merchants" / "laferia"
    / "templates" / "objections"
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="gaucho-cache")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("classify", help="route one utterance")
    c.add_argument("text")
    c.add_argument("--stage", required=True)
    c.add_argument("--index", type=Path, default=DEFAULT_INDEX)
    c.add_argument("--thresholds", type=Path, default=DEFAULT_THRESHOLDS)
    c.add_argument("--contracts", type=Path, default=DEFAULT_CONTRACTS)

    args = ap.parse_args(argv)

    if not args.index.exists():
        print(f"index not found: {args.index} (run scripts/build_index.py)",
              file=sys.stderr)
        return 2

    clf = Classifier(
        index=StageIndex.load(args.index),
        contracts=load_contracts(args.contracts,
                                 REPO_ROOT / "data" / "contract_extensions.yaml"),
        thresholds=load_thresholds(args.thresholds),
    )
    print(clf.classify(args.text, stage=args.stage).to_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
