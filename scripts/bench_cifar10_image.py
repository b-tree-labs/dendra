# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0

"""CIFAR-10 image bench. Generates a paired-correctness JSONL the
existing figure scripts can consume.

Output: docs/papers/2026-when-should-a-rule-learn/results/cifar10_paired.jsonl
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from dendra.benchmarks.loaders import load_cifar10
from dendra.image_rules import build_color_centroid_rule
from dendra.ml import ImagePixelLogRegHead


@dataclass
class _Rec:
    input: np.ndarray
    label: str
    outcome: str = "correct"


CHECKPOINTS = [50, 100, 250, 500, 1000, 2000, 4000]
TRAIN_N = max(CHECKPOINTS)
TEST_N = 500


def main() -> int:
    print("loading CIFAR-10 ...")
    ds = load_cifar10(train_n=TRAIN_N, test_n=TEST_N)
    print(f"  train={len(ds.train)} test={len(ds.test)}")

    rule = build_color_centroid_rule(ds.train[:100])
    rule_correct = [rule(img) == lbl for img, lbl in ds.test]
    rule_acc = sum(rule_correct) / len(rule_correct)
    print(f"  rule (color-centroid, seed=100) accuracy: {rule_acc:.4f}")

    out_path = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "papers"
        / "2026-when-should-a-rule-learn"
        / "results"
        / "cifar10_paired.jsonl"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    citation = "Krizhevsky 2009, 'Learning Multiple Layers of Features from Tiny Images'"
    with out_path.open("w") as fh:
        fh.write(
            json.dumps(
                {
                    "kind": "summary",
                    "benchmark": "cifar10",
                    "labels": len(ds.labels),
                    "train_rows": len(ds.train),
                    "test_rows": len(ds.test),
                    "seed_size": 100,
                    "rule": "color-centroid mean-RGB nearest-neighbor",
                    "ml_head": "ImagePixelLogRegHead (sklearn LogReg on flat pixels)",
                    "checkpoint_every": "explicit list",
                    "citation": citation,
                }
            )
            + "\n"
        )

        for n in CHECKPOINTS:
            head = ImagePixelLogRegHead(min_outcomes=10)
            records = [_Rec(img, lbl) for img, lbl in ds.train[:n]]
            head.fit(records)
            ml_correct = []
            for img, true_lbl in ds.test:
                pred = head.predict(img, list(ds.labels))
                ml_correct.append(pred.label == true_lbl)
            ml_acc = sum(ml_correct) / len(ml_correct)
            print(f"  ckpt {n:5d}: rule={rule_acc:.4f}  ml={ml_acc:.4f}")
            fh.write(
                json.dumps(
                    {
                        "kind": "checkpoint",
                        "training_outcomes": n,
                        "rule_test_accuracy": rule_acc,
                        "ml_test_accuracy": ml_acc,
                        "ml_trained": True,
                        "ml_version": head.model_version(),
                        "model_test_accuracy": None,
                        "lm_test_sample": None,
                        "rule_correct": rule_correct,
                        "ml_correct": ml_correct,
                    }
                )
                + "\n"
            )
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
