# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0

"""ML head protocol + default scikit-learn head.

Phase 3 (ML_SHADOW), Phase 4 (ML_WITH_FALLBACK), and Phase 5 (ML_PRIMARY)
use an :class:`MLHead` to produce classifications. The protocol is
intentionally narrow: ``fit(outcomes)``, ``predict(input, labels)``, and
``model_version()``. Any backend that satisfies the protocol can be
plugged in — sklearn, ONNX-runtime, a remote inference service, or a
fake for tests.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class MLPrediction:
    """What an ML head returns for one input."""

    label: str
    confidence: float


@runtime_checkable
class MLHead(Protocol):
    """Pluggable ML classifier backend."""

    def fit(self, records: Iterable[Any]) -> None: ...

    def predict(self, input: Any, labels: Iterable[str]) -> MLPrediction: ...

    def model_version(self) -> str: ...


# ---------------------------------------------------------------------------
# Default sklearn head — optional, lazy-imported.
# ---------------------------------------------------------------------------


class SklearnTextHead:
    """Simple TF-IDF + logistic-regression text classifier.

    Used as the zero-config default for text-input switches. Serializes
    inputs with ``repr(input)`` which works well for dict/str/number
    inputs; users with structured inputs should supply their own
    :class:`MLHead`.
    """

    def __init__(self, *, min_outcomes: int = 50) -> None:
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.linear_model import LogisticRegression
            from sklearn.pipeline import Pipeline
        except ImportError as e:
            raise ImportError(
                "SklearnTextHead requires scikit-learn. Install with `pip install dendra[train]`."
            ) from e
        self._Pipeline = Pipeline
        self._Tfidf = TfidfVectorizer
        self._LR = LogisticRegression
        self._pipeline: Any | None = None
        self._min_outcomes = min_outcomes
        self._version = "sklearn-untrained"

    def fit(self, records: Iterable[Any]) -> None:
        records = list(records)
        if len(records) < self._min_outcomes:
            return
        # Use the actual observed label (the `output`) as the training
        # target when the outcome was correct; drop rows we know are wrong
        # so the head doesn't learn to reproduce mistakes.
        X, y = [], []
        for r in records:
            if getattr(r, "outcome", None) != "correct":
                continue
            X.append(serialize_input_for_features(r.input))
            y.append(r.output)
        if len({*y}) < 2:
            return
        pipe = self._Pipeline(
            [
                ("tfidf", self._Tfidf(min_df=1)),
                ("clf", self._LR(max_iter=1000)),
            ]
        )
        pipe.fit(X, y)
        self._pipeline = pipe
        self._version = f"sklearn-{len(records)}"

    def predict(self, input: Any, labels: Iterable[str]) -> MLPrediction:
        if self._pipeline is None:
            # Untrained — surface a low-confidence guess so the caller
            # routes to the fallback.
            return MLPrediction(label="", confidence=0.0)
        probs = self._pipeline.predict_proba([serialize_input_for_features(input)])[0]
        classes = list(self._pipeline.classes_)
        idx = int(probs.argmax())
        return MLPrediction(label=classes[idx], confidence=float(probs[idx]))

    def model_version(self) -> str:
        return self._version


def serialize_input_for_features(value: Any) -> str:
    """Turn an arbitrary Dendra classifier input into a feature string.

    Rules, in order (most→least specific):

    1. ``str`` — passed through.
    2. ``dict`` — each ``k: v`` pair joined, string values rendered raw,
       nested dicts recursed, other types repr'd. Preserves key names so
       TF-IDF tokenization can weight ``title:`` hits vs ``body:`` hits.
    3. ``list`` / ``tuple`` — elements joined by spaces after recursing.
    4. ``None`` — empty string.
    5. Anything else — ``repr(value)`` as a universal fallback.

    This is the module's *auto feature extraction* for text-oriented ML
    heads. The philosophy: do something sensible by default so adopters
    who pass "realistic" classifier inputs (strings, ticket dicts,
    trimmed records) get decent features without writing a pipeline.
    Advanced users plug a custom :class:`MLHead` and take over entirely.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        parts = []
        for k, v in value.items():
            parts.append(f"{k}: {serialize_input_for_features(v)}")
        return " | ".join(parts)
    if isinstance(value, (list, tuple)):
        return " ".join(serialize_input_for_features(v) for v in value)
    if isinstance(value, (int, float, bool)):
        return repr(value)
    return repr(value)


__all__ = [
    "MLHead",
    "MLPrediction",
    "SklearnTextHead",
    "serialize_input_for_features",
]
