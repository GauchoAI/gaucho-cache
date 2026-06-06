"""Decision and match contracts (PLAN.md §§10-13).

The MatchContract is parsed from the merchant template's YAML
frontmatter — the merchant overlay is the single source of truth for
``audited``, ``prohibited_topics`` etc. (§13.1). This module never
maintains a parallel store; it loads and extends what the templates
already declare.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

import yaml


def default_contracts_dir(repo_root: Path) -> Path:
    """Resolve the merchant templates directory, standalone-friendly.

    Order: $GAUCHO_CACHE_CONTRACTS → live agentic-crm sibling checkout →
    the vendored snapshot under examples/ (committed, so a fresh clone
    works with no sibling repo).
    """
    env = os.environ.get("GAUCHO_CACHE_CONTRACTS")
    if env:
        return Path(env)
    live = (repo_root.parent / "agentic-crm" / "merchants" / "laferia"
            / "templates" / "objections")
    if live.exists():
        return live
    return repo_root / "examples" / "laferia" / "objections"


@dataclass(frozen=True)
class MatchContract:
    """Per-template serving contract, parsed from frontmatter.

    Core keys exist in production templates today (agentic-crm,
    `merchants/<m>/templates/objections/*.md`); the optional keys are
    Gaucho Caché extensions a template MAY declare (§13.1).
    """

    template_id: str            # frontmatter `id`, e.g. "WARRANTY-v1"
    category: str               # intent name, e.g. "warranty"
    version: int
    audited: bool
    prohibited_topics: tuple[str, ...] = ()
    required_placeholders: tuple[str, ...] = ()
    # Gaucho Caché extensions (optional in frontmatter):
    allowed_stages: tuple[str, ...] = ()      # empty = any stage
    required_state_fields: tuple[str, ...] = ()
    body: str = field(default="", repr=False)
    source_path: str = ""

    def preconditions_pass(self, *, stage: str, state_fields: set[str] | None = None) -> tuple[bool, str]:
        """Evaluate the non-semantic legs of the hit predicate."""
        if self.allowed_stages and stage not in self.allowed_stages:
            return False, "stage_not_allowed"
        missing = set(self.required_state_fields) - (state_fields or set())
        if missing:
            return False, "precondition_failed"
        return True, ""


@dataclass(frozen=True)
class IntentSpec:
    """One classifier target: a (stage, intent) cell of the taxonomy."""

    stage: str
    intent: str
    meaning: str                       # what the customer is expressing
    confusables: tuple[str, ...] = ()  # adjacent intents for hard negatives
    template_file: str = ""            # relative to the contracts dir


@dataclass
class CacheDecision:
    """The library/CLI output contract (§§10, 12)."""

    decision: str                  # "hit" | "miss"
    stage: str
    intent: str | None = None
    score: float | None = None
    margin: float | None = None            # top1 - top2 (distinct intent)
    negative_margin: float | None = None   # top1 - nearest negative of top1
    nearest_negative: str | None = None    # actual_intent of that negative
    template_id: str | None = None
    template_version: str | None = None
    audited: bool | None = None
    preconditions_passed: bool | None = None
    serve_eligible: bool = False
    reason: str = ""               # which predicate leg failed, "" on serve

    def to_json(self) -> str:
        d = {k: v for k, v in asdict(self).items() if v is not None}
        return json.dumps(d, ensure_ascii=False)


def parse_frontmatter(path: Path) -> MatchContract:
    """Parse one merchant template (`---` YAML frontmatter + body)."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise ValueError(f"{path}: no YAML frontmatter")
    _, fm, body = text.split("---", 2)
    meta = yaml.safe_load(fm)
    return MatchContract(
        template_id=str(meta["id"]),
        category=str(meta["category"]),
        version=int(meta.get("version", 1)),
        audited=bool(meta.get("audited", False)),
        prohibited_topics=tuple(meta.get("prohibited_topics") or ()),
        required_placeholders=tuple(meta.get("required_placeholders") or ()),
        allowed_stages=tuple(meta.get("allowed_stages") or ()),
        required_state_fields=tuple(meta.get("required_state_fields") or ()),
        body=body.strip(),
        source_path=str(path),
    )


def load_contracts(contracts_dir: Path,
                   extensions_path: Path | None = None) -> dict[str, MatchContract]:
    """Load every template in a directory, keyed by category (intent).

    ``extensions_path`` points to a YAML of Gaucho Caché-side contract
    extensions ({category: {required_state_fields: [...], ...}}) so
    serving preconditions can be tightened without editing the
    merchant's audited template files.
    """
    ext: dict = {}
    if extensions_path and extensions_path.exists():
        ext = yaml.safe_load(extensions_path.read_text(encoding="utf-8")) or {}
    contracts: dict[str, MatchContract] = {}
    for p in sorted(contracts_dir.glob("*.md")):
        c = parse_frontmatter(p)
        e = ext.get(c.category) or {}
        if e:
            c = MatchContract(
                template_id=c.template_id, category=c.category,
                version=c.version, audited=c.audited,
                prohibited_topics=c.prohibited_topics,
                required_placeholders=c.required_placeholders,
                allowed_stages=tuple(e.get("allowed_stages")
                                     or c.allowed_stages),
                required_state_fields=tuple(e.get("required_state_fields")
                                            or c.required_state_fields),
                body=c.body, source_path=c.source_path,
            )
        contracts[c.category] = c
    return contracts


def load_all_contracts(repo_root: Path,
                       extensions_path: Path | None = None) -> dict[str, MatchContract]:
    """Merchant objection templates + the global conversational intents
    (greet / thanks / store-info, owned cache-side under
    data/templates_globals/ until the merchant overlay adopts them)."""
    contracts = load_contracts(default_contracts_dir(repo_root), extensions_path)
    globals_dir = repo_root / "data" / "templates_globals"
    if globals_dir.exists():
        contracts.update(load_contracts(globals_dir, extensions_path))
    return contracts


def load_intent_specs(path: Path) -> list[IntentSpec]:
    """Load the slice taxonomy YAML (list of IntentSpec dicts)."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [
        IntentSpec(
            stage=item["stage"],
            intent=item["intent"],
            meaning=item["meaning"],
            confusables=tuple(item.get("confusables") or ()),
            template_file=item.get("template_file", ""),
        )
        for item in raw["intents"]
    ]
