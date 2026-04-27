"""Autoresearch loop: pick the best MLHead empirically on Dendra's own benchmarks.

Uses the same paired-McNemar gate the paper publishes about. Four
candidate heads (TF-IDF + LogisticRegression / LinearSVC /
MultinomialNB / GradientBoosting) compete head-to-head against the
incumbent (TfidfLogReg). The McNemar gate at alpha=0.01 chooses the
empirical winner per benchmark.

Outputs ``docs/papers/2026-when-should-a-rule-learn/results/
autoresearch-mlhead-<bench>.json`` so the paper can cite a real
machine-decided MLHead pick rather than a hand-waved default.

Run:
    python scripts/autoresearch_mlhead.py [bench_slug ...]

If no slugs are provided, runs all five benchmarks.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from dendra.ml import (
    SklearnTextHead,
    TfidfGradientBoostingHead,
    TfidfLinearSVCHead,
    TfidfMultinomialNBHead,
)


RESULTS_DIR = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "papers"
    / "2026-when-should-a-rule-learn"
    / "results"
)
INCUMBENT = "TfidfLogReg"


@dataclass
class _TrainRec:
    """Minimal record shape the heads' fit() understands."""

    input: str
    label: str
    outcome: str = "correct"


@dataclass
class CandidateReport:
    name: str
    accuracy: float
    mcnemar_p: float
    discordant_b: int
    discordant_c: int
    n_test: int
    correct_count: int

    def cleared_against_incumbent(self, alpha: float) -> bool:
        return (
            self.discordant_b > self.discordant_c
            and self.mcnemar_p < alpha
        )


@dataclass
class SelectionResult:
    winner_name: str
    reports: dict[str, CandidateReport]
    alpha: float
    benchmark: str | None = None
    n_train: int = 0
    n_test: int = 0
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "winner": self.winner_name,
            "alpha": self.alpha,
            "benchmark": self.benchmark,
            "n_train": self.n_train,
            "n_test": self.n_test,
            "rationale": self.rationale,
            "reports": {name: asdict(r) for name, r in self.reports.items()},
        }


def _candidate_factory() -> dict[str, Any]:
    """Fresh candidates every call so retraining is a clean slate."""
    return {
        INCUMBENT: SklearnTextHead(min_outcomes=10),
        "TfidfLinearSVC": TfidfLinearSVCHead(min_outcomes=10),
        "TfidfMultinomialNB": TfidfMultinomialNBHead(min_outcomes=10),
        "TfidfGradientBoosting": TfidfGradientBoostingHead(min_outcomes=10),
    }


def _paired_mcnemar_p(b: int, c: int) -> float:
    """Two-sided exact-binomial McNemar p-value on (b, c) discordant counts."""
    n = b + c
    if n == 0:
        return 1.0
    from scipy.stats import binom

    k = min(b, c)
    return min(1.0, 2.0 * float(binom.cdf(k, n, 0.5)))


def select_best_head(
    train_records: Iterable[Any],
    test_pairs: Iterable[tuple[str, str]],
    *,
    alpha: float = 0.01,
) -> SelectionResult:
    """Train every candidate, run the paired-McNemar gate vs incumbent.

    Returns a :class:`SelectionResult` whose ``winner_name`` is the
    accuracy-leading candidate that clears the gate against the
    incumbent at significance ``alpha``. If no challenger clears, the
    incumbent wins.
    """
    train_records = list(train_records)
    test_pairs = list(test_pairs)
    candidates = _candidate_factory()

    for head in candidates.values():
        head.fit(train_records)

    labels = sorted({lbl for _, lbl in test_pairs})

    correctness: dict[str, list[bool]] = {}
    for name, head in candidates.items():
        correct: list[bool] = []
        for text, true_label in test_pairs:
            pred = head.predict(text, labels)
            correct.append(pred.label == true_label)
        correctness[name] = correct

    incumbent_correct = correctness[INCUMBENT]
    n_test = len(test_pairs)

    reports: dict[str, CandidateReport] = {}
    for name, correct in correctness.items():
        if name == INCUMBENT:
            reports[name] = CandidateReport(
                name=name,
                accuracy=sum(correct) / n_test if n_test else 0.0,
                mcnemar_p=1.0,
                discordant_b=0,
                discordant_c=0,
                n_test=n_test,
                correct_count=sum(correct),
            )
            continue
        b = sum(1 for ci, cc in zip(incumbent_correct, correct) if cc and not ci)
        c = sum(1 for ci, cc in zip(incumbent_correct, correct) if ci and not cc)
        reports[name] = CandidateReport(
            name=name,
            accuracy=sum(correct) / n_test if n_test else 0.0,
            mcnemar_p=_paired_mcnemar_p(b, c),
            discordant_b=b,
            discordant_c=c,
            n_test=n_test,
            correct_count=sum(correct),
        )

    cleared = [
        (name, r)
        for name, r in reports.items()
        if name != INCUMBENT and r.cleared_against_incumbent(alpha)
    ]
    if cleared:
        winner_name, _ = max(cleared, key=lambda nr: nr[1].accuracy)
        rationale = (
            f"{winner_name} cleared paired-McNemar at alpha={alpha} vs "
            f"{INCUMBENT} and had the highest accuracy among cleared "
            f"challengers"
        )
    else:
        winner_name = INCUMBENT
        rationale = (
            f"no challenger cleared paired-McNemar at alpha={alpha} vs "
            f"{INCUMBENT}; incumbent retained"
        )

    return SelectionResult(
        winner_name=winner_name,
        reports=reports,
        alpha=alpha,
        n_train=len(train_records),
        n_test=n_test,
        rationale=rationale,
    )


def run_autoresearch(benchmark_slug: str, *, alpha: float = 0.01) -> SelectionResult:
    """Run the autoresearch loop on a public benchmark."""
    from dendra.benchmarks import loaders

    loader = getattr(loaders, f"load_{benchmark_slug}", None)
    if loader is None:
        raise ValueError(f"unknown benchmark slug: {benchmark_slug}")

    ds = loader()
    train_records = [_TrainRec(text, lbl) for text, lbl in ds.train]

    result = select_best_head(train_records, ds.test, alpha=alpha)
    result.benchmark = benchmark_slug
    return result


def _save(result: SelectionResult) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"autoresearch-mlhead-{result.benchmark}.json"
    out.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return out


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    benches = argv or ["atis", "snips", "hwu64", "banking77", "clinc150"]
    for slug in benches:
        print(f"==> autoresearch on {slug}")
        result = run_autoresearch(slug)
        out = _save(result)
        print(f"    winner: {result.winner_name}")
        for name, report in result.reports.items():
            mark = " *" if name == result.winner_name else "  "
            print(
                f"    {mark} {name:24s} acc={report.accuracy:.4f} "
                f"p={report.mcnemar_p:.2e}  b={report.discordant_b:5d} c={report.discordant_c:5d}"
            )
        print(f"    saved -> {out.relative_to(Path.cwd()) if out.is_relative_to(Path.cwd()) else out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
