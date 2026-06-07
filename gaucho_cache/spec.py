"""Domain spec: the signable markdown a domain is defined by.

The user's shape: an agent interviews the owner — what's your funnel?
which stages? which facts are constitutional? what may never be
promised? — and emits a markdown the owner SIGNS and sends for training.
This module is the contract that markdown obeys: a YAML frontmatter the
whole system reads (FSM stages, the EXPECTED_NEXT context map, class-B
fact sources, the red lines the safety benchmark enforces, the
certification targets the pipeline must clear), followed by free prose
the onboarding agent and the merchant can both read.

A spec is the single source of truth for one domain. `Domain.from_spec`
loads it; `train(spec)` distills/builds against it; the adversarial
benchmark draws its red lines from it; the FSM-as-data (chapter E) reads
its stages. No hand-edited Python per domain — the spec is the knob.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
SPECS = REPO / "data" / "specs"


@dataclass
class DomainSpec:
    name: str
    description: str = ""
    stages: list[str] = field(default_factory=list)
    # intent -> intents the bot's last turn invites (the context map)
    expected_next: dict[str, list[str]] = field(default_factory=dict)
    # clusters whose in-confusions are harmless (greet/thanks/... lineage)
    safe_clusters: list[list[str]] = field(default_factory=list)
    # files (relative to repo) holding the merchant facts class-B renders
    fact_sources: dict[str, str] = field(default_factory=dict)
    # things the bot must NEVER say/offer — the adversarial red lines
    red_lines: list[str] = field(default_factory=list)
    # certification floor the pipeline must clear
    certify_recall: float = 0.60
    certify_max_fp: int = 0
    signed_by: str = ""
    body: str = ""

    @classmethod
    def load(cls, name_or_path: str | Path) -> "DomainSpec":
        p = Path(name_or_path)
        if not p.exists():
            p = SPECS / f"{name_or_path}.md"
        text = p.read_text(encoding="utf-8")
        fm, body = _split_frontmatter(text)
        d = yaml.safe_load(fm) or {}
        return cls(
            name=d["name"], description=d.get("description", ""),
            stages=d.get("stages", []),
            expected_next=d.get("expected_next", {}),
            safe_clusters=d.get("safe_clusters", []),
            fact_sources=d.get("fact_sources", {}),
            red_lines=d.get("red_lines", []),
            certify_recall=float(d.get("certify_recall", 0.60)),
            certify_max_fp=int(d.get("certify_max_fp", 0)),
            signed_by=d.get("signed_by", ""), body=body.strip())

    def is_signed(self) -> bool:
        return bool(self.signed_by)

    def save(self, path: Path | None = None) -> Path:
        SPECS.mkdir(parents=True, exist_ok=True)
        path = path or SPECS / f"{self.name}.md"
        fm = {"name": self.name, "description": self.description,
              "stages": self.stages, "expected_next": self.expected_next,
              "safe_clusters": self.safe_clusters,
              "fact_sources": self.fact_sources, "red_lines": self.red_lines,
              "certify_recall": self.certify_recall,
              "certify_max_fp": self.certify_max_fp}
        if self.signed_by:
            fm["signed_by"] = self.signed_by
        path.write_text("---\n" + yaml.safe_dump(fm, allow_unicode=True,
                                                 sort_keys=False)
                        + "---\n\n" + self.body + "\n", encoding="utf-8")
        return path


def _split_frontmatter(text: str) -> tuple[str, str]:
    if text.startswith("---"):
        _, fm, body = text.split("---", 2)
        return fm, body
    return "", text


# ---- the onboarding interview (questions an agent walks the owner through) --
INTERVIEW = [
    ("name", "A short slug for this domain (e.g. 'recepcion', 'sales')."),
    ("description", "One line: what does this assistant do, for whom?"),
    ("stages", "The funnel stages in order. A sales bot might be "
               "awareness→interest→desire→action; a receptionist might be "
               "greet→inquire→answer→book. List yours."),
    ("facts", "Which facts are constitutional — must always be exact? "
              "(hours, address, prices, catalog, coverage). Point me at "
              "each source file or paste them."),
    ("red_lines", "What may the bot NEVER say or offer? (discounts beyond "
                  "the ladder, certifications you don't have, promises you "
                  "can't keep). These become adversarial tests."),
    ("targets", "Certification floor: minimum fresh-paraphrase recall "
                "(default 60%) and max false positives (default 0)."),
]


def apply_fsm(spec: "DomainSpec") -> dict:
    """FSM-as-data: install a spec's context map and safe clusters into the
    live predicate, replacing the hand-edited constants (chapter E). Returns
    what changed, for verification. The sales spec reproduces the mattress
    behaviour exactly — proof the constants were always just this data."""
    from . import classifier as C
    before = {"expected_next": dict(C.EXPECTED_NEXT),
              "social": set(C.SOCIAL), "funnel": set(C.FUNNEL)}
    if spec.expected_next:
        C.EXPECTED_NEXT = {k: tuple(v) for k, v in spec.expected_next.items()}
    clusters = [set(c) for c in spec.safe_clusters]
    # first cluster containing 'greet' (or the first) is the social cluster;
    # a cluster of funnel intents (want_to_buy/answer_*) is the funnel one
    for c in clusters:
        if "greet" in c or "thanks_goodbye" in c:
            C.SOCIAL = c
        elif c & {"want_to_buy", "answer_size_posture", "ask_recommendation"}:
            C.FUNNEL = c
    return {"before": before,
            "after": {"expected_next_keys": sorted(C.EXPECTED_NEXT),
                      "social": sorted(C.SOCIAL), "funnel": sorted(C.FUNNEL)}}


def spec_template(name: str = "your-domain") -> str:
    """A blank spec for the onboarding agent to fill, with guidance."""
    return DomainSpec(
        name=name,
        description="<one line>",
        stages=["<stage1>", "<stage2>", "..."],
        expected_next={"<stageN>": ["<intent the bot then invites>"]},
        safe_clusters=[["greet", "thanks", "confirmation"]],
        fact_sources={"catalog": "data/<name>/catalog.json"},
        red_lines=["<a promise the bot must never make>"],
        body="## Notes\n\n<context the onboarding agent gathered>\n\n"
             "## Signature\n\nSigned: <owner> on <date>",
    ).save(SPECS / f"{name}.template.md").read_text()
