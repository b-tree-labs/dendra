# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0

"""Loaders for public intent-classification benchmarks.

Each loader returns a :class:`BenchmarkDataset` with a uniform shape so
downstream Dendra evaluation code doesn't care which corpus it's using.

The optional ``datasets`` library (HuggingFace) is imported lazily per-call;
if it isn't installed a clear ImportError is raised pointing the user at the
``bench`` extra.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

CACHE_DIR = Path.home() / ".cache" / "dendra" / "datasets"

_INSTALL_HINT = (
    "The 'datasets' library is required for Dendra benchmark loaders. "
    "Install it with:  pip install dendra[bench]"
)


@dataclass
class BenchmarkDataset:
    """Uniform shape for all four intent-classification benchmarks."""

    name: str
    train: list[tuple[str, str]]
    test: list[tuple[str, str]]
    labels: list[str] = field(default_factory=list)
    citation: str = ""


def _require_datasets() -> Any:
    try:
        from datasets import load_dataset  # type: ignore[import-not-found]
    except ImportError as e:  # pragma: no cover
        raise ImportError(_INSTALL_HINT) from e
    return load_dataset


def _load(hf_id: str, config: Optional[str] = None) -> Any:
    load_dataset = _require_datasets()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if config:
        return load_dataset(hf_id, config, cache_dir=str(CACHE_DIR))
    return load_dataset(hf_id, cache_dir=str(CACHE_DIR))


def _rows_to_pairs(
    split: Any, text_key: str, label_key: str, label_names: list[str]
) -> list[tuple[str, str]]:
    """Normalize a split to (text, label_string) pairs.

    Handles both ``ClassLabel`` (int + names) and plain string labels.
    """
    out: list[tuple[str, str]] = []
    for row in split:
        raw = row[label_key]
        if isinstance(raw, int) and label_names:
            label = label_names[raw]
        else:
            label = str(raw)
        out.append((row[text_key], label))
    return out


def _collect_string_labels(pairs: list[tuple[str, str]]) -> list[str]:
    seen: list[str] = []
    s = set()
    for _, lbl in pairs:
        if lbl not in s:
            s.add(lbl)
            seen.append(lbl)
    return sorted(seen)


def load_banking77() -> BenchmarkDataset:
    """Banking77 (Casanueva et al. 2020) — 77 fine-grained banking intents."""
    ds = _load("banking77")
    label_feat = ds["train"].features["label"]
    names = list(getattr(label_feat, "names", []))
    train = _rows_to_pairs(ds["train"], "text", "label", names)
    test = _rows_to_pairs(ds["test"], "text", "label", names)
    labels = names or _collect_string_labels(train + test)
    return BenchmarkDataset(
        name="banking77",
        train=train,
        test=test,
        labels=labels,
        citation="Casanueva et al. 2020, 'Efficient Intent Detection with Dual Sentence Encoders'",
    )


def load_clinc150() -> BenchmarkDataset:
    """CLINC150 (Larson et al. 2019) — 150 intents + out-of-scope = 151 labels."""
    ds = _load("clinc_oos", "plus")
    label_feat = ds["train"].features["intent"]
    names = list(getattr(label_feat, "names", []))
    train = _rows_to_pairs(ds["train"], "text", "intent", names)
    test = _rows_to_pairs(ds["test"], "text", "intent", names)
    labels = names or _collect_string_labels(train + test)
    return BenchmarkDataset(
        name="clinc150",
        train=train,
        test=test,
        labels=labels,
        citation="Larson et al. 2019, 'An Evaluation Dataset for Intent Classification and Out-of-Scope Prediction'",
    )


def _maybe_names(feat: Any) -> list[str]:
    return list(getattr(feat, "names", []) or [])


def load_hwu64() -> BenchmarkDataset:
    """HWU64 (Liu et al. 2019) — 64 intents across 21 scenarios."""
    ds = _load("FastFit/hwu_64")
    names = _maybe_names(ds["train"].features["label"])
    train = _rows_to_pairs(ds["train"], "text", "label", names)
    test_split = ds["test"] if "test" in ds else ds["validation"]
    test = _rows_to_pairs(test_split, "text", "label", names)
    labels = names or _collect_string_labels(train + test)
    return BenchmarkDataset(
        name="hwu64",
        train=train,
        test=test,
        labels=labels,
        citation="Liu et al. 2019, 'Benchmarking Natural Language Understanding Services for Building Conversational Agents'",
    )


def load_atis() -> BenchmarkDataset:
    """ATIS — Air Travel Information System; ~17–26 flight-domain intents."""
    ds = _load("tuetschek/atis")
    names = _maybe_names(ds["train"].features["intent"])
    train = _rows_to_pairs(ds["train"], "text", "intent", names)
    test_split = ds["test"] if "test" in ds else ds["validation"]
    test = _rows_to_pairs(test_split, "text", "intent", names)
    labels = names or _collect_string_labels(train + test)
    return BenchmarkDataset(
        name="atis",
        train=train,
        test=test,
        labels=labels,
        citation="Hemphill et al. 1990, 'The ATIS Spoken Language Systems Pilot Corpus'",
    )
