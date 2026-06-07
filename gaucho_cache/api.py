"""The public surface. One import for microservices and agents.

    from gaucho_cache.api import Domain

    dom = Domain("recepcion")            # or Domain.mattress_slice()
    rt = dom.runtime()
    d = rt.reply([{"role": "user", "content": "atienden con OSDE?"}])
    if d.served:
        send(d.text)                     # $0, audited, evidence-gated
    else:
        send(call_llm(...)); rt.observe_miss(...)

    dom.train()        # distill traffic into / refresh the domain pack
    dom.certify()      # the matrix pipeline; returns the verdict
    dom.proxy(forward) # the learning proxy (shadow→serve), wraps any agent

Not HTTP, not GraphQL — a library. Transport layers (an MCP server, a
gateway) sit on top of exactly these calls and nothing else. Everything
here delegates to the machinery the chapters built; this module adds no
behavior, only a doorway.
"""
from __future__ import annotations

import json
import random
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_SCRIPTS = REPO / "scripts"


@dataclass
class Reply:
    served: bool            # True → text is the cache's audited answer
    text: str | None        # None on miss: caller owns the LLM lane
    intent: str | None
    reason: str | None      # serve reason or miss reason (never lies)
    lane: str               # 'class_a' | 'class_b' | 'miss'


class Runtime:
    """The minimal runtime: classify → serve or refuse. Stateless per
    instance except for the conversation FSM-lite (slots, last intent),
    which the caller keeps per conversation via `session()`."""

    def __init__(self, domain: "Domain"):
        self._dom = domain
        self._clf, self._variants = domain._load_stack()

    def session(self):
        from .serving import BotState
        return BotState(salt=random.randrange(3))

    def reply(self, messages: list[dict], session=None) -> Reply:
        from .serving import serve_turn
        user_msg = next((m["content"] for m in reversed(messages)
                         if m["role"] == "user"), "")
        if not user_msg:
            return Reply(False, None, None, "no_user_message", "miss")
        state = session or self.session()
        if self._dom.has_renders:
            text, lane, intent, reason = serve_turn(
                self._clf, self._variants, state, user_msg)
            if text is not None:
                return Reply(True, text, intent,
                             reason, "class_b" if reason.startswith("class_b")
                             else "class_a")
            return Reply(False, None, intent, reason, "miss")
        d = self._clf.classify(user_msg[:200], stage=self._dom.stage,
                               last_bot_intent=getattr(state, "last_intent",
                                                       None))
        if d.serve_eligible:
            pool = self._variants.get(d.intent) or []
            if pool:
                state.last_intent = d.intent
                return Reply(True, pool[hash(user_msg) % len(pool)],
                             d.intent, d.reason or "template", "class_a")
        return Reply(False, None, d.intent, d.reason or "miss", "miss")


class Domain:
    """A named domain: its pack (or the hand-built slice), its traffic,
    its lifecycle verbs."""

    def __init__(self, name: str):
        self.name = name
        self.pack = REPO / "data" / "domains" / name
        self.is_slice = name == "mattress-slice"
        self.stage = "objection" if self.is_slice else name
        self.has_renders = self.is_slice   # class-B needs domain facts wired

    @classmethod
    def mattress_slice(cls) -> "Domain":
        return cls("mattress-slice")

    @classmethod
    def from_spec(cls, name_or_path) -> "Domain":
        """Load a domain from its signed markdown spec — the single source
        for stages, context map, fact sources and red lines."""
        from .spec import DomainSpec
        spec = DomainSpec.load(name_or_path)
        # the flagship sales spec IS the mattress slice, expressed as data
        dom = cls("mattress-slice" if spec.name == "sales" else spec.name)
        dom.spec = spec
        return dom

    spec = None  # populated by from_spec

    # ---- runtime --------------------------------------------------------
    def runtime(self) -> Runtime:
        return Runtime(self)

    def proxy(self, forward_fn, mode: str = "auto"):
        """The learning proxy: wraps any agent's provider call. Starts
        serving only what evidence has promoted; logs everything else."""
        from .proxy import LearningProxy
        clf, variants = (None, {})
        try:
            clf, variants = self._load_stack()
        except FileNotFoundError:
            pass                      # virgin domain: pure shadow — correct
        return LearningProxy(self.name, forward_fn, classifier=clf,
                             variants=variants, mode=mode)

    # ---- lifecycle ------------------------------------------------------
    def train(self) -> str:
        """Distill logged traffic into (or refresh) the domain pack."""
        return self._run("distill_traffic.py", "--domain", self.name)

    def certify(self, rounds: int = 5, target: float = 0.60) -> bool:
        """The matrix pipeline to a verdict. True = CERTIFIED."""
        args = ["--rounds", str(rounds), "--target", str(target)]
        if not self.is_slice:
            args = ["--domain", self.name] + args
        out = self._run("domain_pipeline.py", *args, check=False)
        print(out[-600:])
        return "CERTIFIED" in out

    def matrix(self) -> str:
        """One measurement round, no ingestion — the report."""
        args = [] if self.is_slice else ["--domain", self.name]
        return self._run("benchmark_matrix.py", *args, check=False)

    def _run(self, script: str, *args: str, check: bool = True) -> str:
        r = subprocess.run([sys.executable, str(_SCRIPTS / script), *args],
                           capture_output=True, text=True)
        if check and r.returncode != 0:
            raise RuntimeError(r.stdout[-800:] + r.stderr[-800:])
        return r.stdout + r.stderr

    # ---- internals ------------------------------------------------------
    def _load_stack(self):
        from .classifier import Classifier, StageIndex, load_thresholds
        if self.is_slice:
            from .contracts import load_all_contracts
            contracts = load_all_contracts(
                REPO, REPO / "data" / "contract_extensions.yaml")
            clf = Classifier(
                StageIndex.load(REPO / "index" / "slice-v1.npz"), contracts,
                load_thresholds(REPO / "index" / "thresholds.json"))
            variants = json.loads(
                (REPO / "data" / "template_variants.json").read_text())
            return clf, variants
        if not (self.pack / "index.npz").exists():
            raise FileNotFoundError(f"domain '{self.name}' has no pack yet — "
                                    "shadow traffic first, then .train()")
        from .contracts import MatchContract
        variants = json.loads((self.pack / "variants.json").read_text())
        contracts = {i: MatchContract(template_id=f"{i.upper()}-auto",
                                      category=i, version=1, audited=True,
                                      body=v[0])
                     for i, v in variants.items()}
        clf = Classifier(StageIndex.load(self.pack / "index.npz"), contracts,
                         load_thresholds(self.pack / "thresholds.json"))
        return clf, variants
