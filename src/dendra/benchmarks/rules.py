# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0

"""Reference rule builder for benchmark experiments.

Paper §4.2: the rule is "deliberately simple" — day-zero engineering-
time rules, not expert-tuned baselines. We build one reproducibly:

1. Take the first N training examples (paper default: 100).
2. For each label appearing in that window, extract its most distinctive
   bag-of-words tokens via per-class TF-style frequencies.
3. Return a closure that scores an input against every label's keyword
   set and returns the top-scoring label, falling back to the dominant
   label in the seed window when no keywords match.

The rule stays a pure function of the input text, captured at construction
time — no training signal leaks from outside the seed window.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass

_TOKEN = re.compile(r"[A-Za-z]{3,}")

_STOPWORDS = frozenset(
    """
    the and for with this that from have your you are can will would should
    could what when where which how why has been was were about into onto
    ours over under they them their there its here than then but our also
    any all out off not one two new get got make made use using used more
    most some such just only very like want need give take find look
    """.split()  # noqa: SIM905 — multiline readability beats a wrapped list literal
)


@dataclass(frozen=True)
class ReferenceRule:
    """Captured rule: label → keyword set + fallback."""

    keywords_per_label: dict[str, frozenset[str]]
    fallback_label: str
    seed_size: int

    def classify(self, text: str) -> str:
        tokens = set(_tokenize(text))
        if not tokens:
            return self.fallback_label
        best_label = self.fallback_label
        best_score = 0
        for label, kws in self.keywords_per_label.items():
            score = len(tokens & kws)
            if score > best_score:
                best_score = score
                best_label = label
        return best_label

    def as_callable(self) -> Callable[[str], str]:
        return self.classify


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text or "") if t.lower() not in _STOPWORDS]


def build_reference_rule(
    train_pairs: Iterable[tuple[str, str]],
    *,
    seed_size: int = 100,
    keywords_per_label: int = 5,
) -> ReferenceRule:
    """Build a :class:`ReferenceRule` from the first ``seed_size`` examples.

    Per-label keyword selection: pick the tokens whose in-label count is
    highest *and* that appear in fewer than 50% of the other labels. This
    keeps the rule biased toward distinctive words without a full TF-IDF.
    """
    seed = list(train_pairs)[:seed_size]
    if not seed:
        raise ValueError("train_pairs must be non-empty")

    per_label_counts: dict[str, Counter] = defaultdict(Counter)
    label_counts: Counter = Counter()
    for text, label in seed:
        tokens = _tokenize(text)
        per_label_counts[label].update(tokens)
        label_counts[label] += 1

    fallback_label, _ = label_counts.most_common(1)[0]

    # Which labels does each token appear in?
    labels_per_token: dict[str, set[str]] = defaultdict(set)
    for label, ctr in per_label_counts.items():
        for tok in ctr:
            labels_per_token[tok].add(label)
    total_labels = len(per_label_counts)
    distinctiveness_cap = max(1, total_labels // 2)

    keywords_per_label_out: dict[str, frozenset[str]] = {}
    for label, ctr in per_label_counts.items():
        ranked: list[tuple[str, int]] = []
        for tok, cnt in ctr.most_common():
            if len(labels_per_token[tok]) > distinctiveness_cap:
                continue
            ranked.append((tok, cnt))
            if len(ranked) >= keywords_per_label:
                break
        keywords_per_label_out[label] = frozenset(tok for tok, _ in ranked)

    return ReferenceRule(
        keywords_per_label=keywords_per_label_out,
        fallback_label=fallback_label,
        seed_size=seed_size,
    )


__all__ = ["ReferenceRule", "build_reference_rule"]
