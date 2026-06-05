"""Embedding classifier with the compound hit predicate (PLAN.md §11.1).

A hit requires ALL of:
    score >= intent_threshold
    top1 - top2(distinct intent)        >= margin_threshold
    top1 - nearest_negative(of top1)    >= negative_margin_threshold
    match-contract preconditions pass
Serving additionally requires the template to be audited (§12).

Index: .npz with normalized float32 embeddings + parallel label arrays.
~1.2k vectors at slice scale — brute-force cosine, no vector DB.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .contracts import CacheDecision, MatchContract

DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_THRESHOLDS = {"threshold": 0.70, "margin": 0.05, "negative_margin": 0.03}


@dataclass
class Thresholds:
    threshold: float
    margin: float
    negative_margin: float


class Embedder:
    """Thin lazy wrapper so importing the package never loads torch."""

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model_name = model_name
        self._model = None

    def encode(self, texts: list[str]) -> np.ndarray:
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        vecs = self._model.encode(texts, normalize_embeddings=True,
                                  show_progress_bar=False)
        return np.asarray(vecs, dtype=np.float32)


class StageIndex:
    """Per-stage embedding index over positive variants + hard negatives."""

    def __init__(self, embeddings: np.ndarray, intents: np.ndarray,
                 kinds: np.ndarray, actual_intents: np.ndarray,
                 model_name: str = DEFAULT_MODEL):
        self.embeddings = embeddings          # (n, d), L2-normalized
        self.intents = intents                # (n,) str — owning intent
        self.kinds = kinds                    # (n,) "positive" | "negative"
        self.actual_intents = actual_intents  # (n,) str — negatives only
        self.model_name = model_name

    @classmethod
    def load(cls, path: Path) -> "StageIndex":
        z = np.load(path, allow_pickle=False)
        return cls(z["embeddings"], z["intents"].astype(str),
                   z["kinds"].astype(str), z["actual_intents"].astype(str),
                   str(z["model_name"][0]))

    def save(self, path: Path) -> None:
        np.savez_compressed(
            path, embeddings=self.embeddings,
            intents=self.intents.astype("U64"), kinds=self.kinds.astype("U16"),
            actual_intents=self.actual_intents.astype("U64"),
            model_name=np.array([self.model_name], dtype="U128"),
        )


def load_thresholds(path: Path | None) -> dict[str, Thresholds]:
    if path is None or not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {k: Thresholds(**v) for k, v in raw.items()}


class Classifier:
    def __init__(self, index: StageIndex,
                 contracts: dict[str, MatchContract],
                 thresholds: dict[str, Thresholds] | None = None,
                 embedder: Embedder | None = None):
        self.index = index
        self.contracts = contracts
        self.thresholds = thresholds or {}
        self.embedder = embedder or Embedder(index.model_name)

    def _thresholds_for(self, intent: str) -> Thresholds:
        return self.thresholds.get(intent, Thresholds(**DEFAULT_THRESHOLDS))

    def route(self, text: str) -> tuple[str, float, float, float, str]:
        """Semantic legs only: (intent, score, margin, neg_margin, nearest_neg_actual)."""
        q = self.embedder.encode([text])[0]
        sims = self.index.embeddings @ q

        pos = self.index.kinds == "positive"
        # Best score per intent over positives.
        best: dict[str, float] = {}
        for intent in np.unique(self.index.intents[pos]):
            m = pos & (self.index.intents == intent)
            best[intent] = float(sims[m].max())
        ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)
        top1_intent, top1 = ranked[0]
        top2 = ranked[1][1] if len(ranked) > 1 else -1.0

        # Nearest hard negative attached to the winning intent.
        neg = (self.index.kinds == "negative") & (self.index.intents == top1_intent)
        if neg.any():
            j = int(np.argmax(np.where(neg, sims, -np.inf)))
            neg_score = float(sims[j])
            neg_actual = str(self.index.actual_intents[j]) or "other"
        else:
            neg_score, neg_actual = -1.0, ""

        return top1_intent, top1, top1 - top2, top1 - neg_score, neg_actual

    def classify(self, text: str, *, stage: str,
                 state_fields: set[str] | None = None) -> CacheDecision:
        intent, score, margin, neg_margin, neg_actual = self.route(text)
        th = self._thresholds_for(intent)
        contract = self.contracts.get(intent)

        d = CacheDecision(
            decision="miss", stage=stage, intent=intent,
            score=round(score, 4), margin=round(margin, 4),
            negative_margin=round(neg_margin, 4),
            nearest_negative=neg_actual or None,
        )
        if contract is not None:
            d.template_id = contract.template_id
            d.template_version = f"v{contract.version}"
            d.audited = contract.audited

        # Compound predicate — first failing leg names the reason.
        if score < th.threshold:
            d.reason = "below_threshold"
            return d
        if margin < th.margin:
            d.reason = "ambiguous_margin"
            return d
        if neg_margin < th.negative_margin:
            d.reason = "negative_margin"
            return d
        if contract is None:
            d.reason = "no_template"
            return d
        ok, why = contract.preconditions_pass(stage=stage, state_fields=state_fields)
        d.preconditions_passed = ok
        if not ok:
            d.reason = why
            return d

        d.decision = "hit"
        if not contract.audited:
            d.reason = "template_unaudited"   # routed, but shadow-only (§12)
            d.serve_eligible = False
        else:
            d.serve_eligible = True
        return d
