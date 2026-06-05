#!/usr/bin/env python3
"""Idempotent sync of the slice artifacts to/from a HuggingFace dataset.

House policy (same as agentic-crm's ``scripts/benchmark/cache_sync.py``):
datasets and caches live on the HF Hub as a versioned dataset so any
machine can reproduce results without regenerating — git carries the
code, HF carries the data, and a snapshot label ties the two together.

Artifacts synced:
    data/slice.sqlite        the curated variant corpus (source of truth)
    index/slice-v1.npz       embedding index (rebuildable from sqlite)
    index/thresholds.json    calibrated per-intent thresholds
    reports/*.md             the four proof reports

Layout on the Hub (dataset repo):
    latest/...                       always the newest snapshot
    snapshots/<label>/...            immutable, label = v1-<git-sha>

Subcommands:
- push   : upload artifacts to snapshots/<label>/ AND latest/.
           Label defaults to v1-<short git sha>. Idempotent — HF
           content-addresses files, unchanged files are no-ops.
- pull   : download latest/ (or --label) into the local tree; existing
           local files are kept unless --refresh.
- status : list local artifacts and remote snapshots. No mutation.

Auth: HF_TOKEN env (write token for push; pull is anonymous if the
dataset is public). Repo from --repo or HF_GAUCHO_CACHE_REPO, default
miguelemosreverte/gaucho-cache.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPO = os.environ.get("HF_GAUCHO_CACHE_REPO",
                              "miguelemosreverte/gaucho-cache")
REPO_TYPE = "dataset"
ARTIFACTS = [
    "data/slice.sqlite",
    "index/slice-v1.npz",
    "index/thresholds.json",
]
REPORT_GLOB = "reports/*.md"


def _token() -> str | None:
    return os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")


def _api():
    from huggingface_hub import HfApi
    return HfApi(token=_token())


def _label() -> str:
    sha = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse",
                          "--short", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    return f"v1-{sha or 'nogit'}"


def _local_artifacts() -> list[Path]:
    paths = [REPO_ROOT / a for a in ARTIFACTS]
    paths += sorted(REPO_ROOT.glob(REPORT_GLOB))
    return [p for p in paths if p.exists()]


def cmd_push(repo: str, label: str) -> int:
    if not _token():
        sys.exit("HF_TOKEN not set — a write token is required for push")
    api = _api()
    api.create_repo(repo, repo_type=REPO_TYPE, exist_ok=True)
    files = _local_artifacts()
    if not files:
        sys.exit("no local artifacts to push — run the pipeline first")
    for prefix in (f"snapshots/{label}", "latest"):
        for p in files:
            rel = p.relative_to(REPO_ROOT)
            api.upload_file(
                path_or_fileobj=str(p),
                path_in_repo=f"{prefix}/{rel}",
                repo_id=repo, repo_type=REPO_TYPE,
                commit_message=f"sync {rel} @ {label}",
            )
    print(f"✓ pushed {len(files)} artifacts to {repo} "
          f"(snapshots/{label} + latest)")
    return 0


def cmd_pull(repo: str, label: str | None, refresh: bool) -> int:
    from huggingface_hub import hf_hub_download
    from huggingface_hub.utils import EntryNotFoundError
    prefix = f"snapshots/{label}" if label else "latest"
    pulled = skipped = 0
    candidates = ARTIFACTS + [f"reports/{n}" for n in (
        "slice-eval.md", "zero-spend-proof.md", "quality-equivalence.md",
        "product-agnostic-check.md")]
    for rel in candidates:
        dest = REPO_ROOT / rel
        if dest.exists() and not refresh:
            skipped += 1
            continue
        try:
            got = hf_hub_download(repo_id=repo, repo_type=REPO_TYPE,
                                  filename=f"{prefix}/{rel}", token=_token())
        except EntryNotFoundError:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(Path(got).read_bytes())
        pulled += 1
    print(f"✓ pulled {pulled} artifacts from {repo}/{prefix} "
          f"({skipped} kept local)")
    return 0


def cmd_status(repo: str) -> int:
    local = _local_artifacts()
    print(f"local: {len(local)} artifacts")
    for p in local:
        print(f"  {p.relative_to(REPO_ROOT)}  {p.stat().st_size/1024:.0f}K")
    try:
        files = _api().list_repo_files(repo, repo_type=REPO_TYPE)
        snaps = sorted({f.split("/")[1] for f in files
                        if f.startswith("snapshots/")})
        print(f"remote {repo}: {len(files)} files, snapshots: {snaps}")
    except Exception as e:  # noqa: BLE001 — status is best-effort
        print(f"remote {repo}: unreachable ({type(e).__name__})")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="hf_sync")
    ap.add_argument("--repo", default=DEFAULT_REPO)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("push")
    p.add_argument("--label", default=None)
    p = sub.add_parser("pull")
    p.add_argument("--label", default=None)
    p.add_argument("--refresh", action="store_true")
    sub.add_parser("status")
    a = ap.parse_args(argv)
    if a.cmd == "push":
        return cmd_push(a.repo, a.label or _label())
    if a.cmd == "pull":
        return cmd_pull(a.repo, a.label, a.refresh)
    return cmd_status(a.repo)


if __name__ == "__main__":
    raise SystemExit(main())
