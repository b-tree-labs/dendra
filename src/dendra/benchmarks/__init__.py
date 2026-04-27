# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0

"""Public intent-classification benchmark loaders.

Requires the optional ``datasets`` dependency: ``pip install dendra[bench]``.
"""

from dendra.benchmarks.loaders import (
    BenchmarkDataset,
    load_ag_news,
    load_atis,
    load_banking77,
    load_cifar10,
    load_clinc150,
    load_codelangs,
    load_hwu64,
    load_snips,
    load_trec6,
)

__all__ = [
    "BenchmarkDataset",
    "load_ag_news",
    "load_atis",
    "load_banking77",
    "load_cifar10",
    "load_clinc150",
    "load_codelangs",
    "load_hwu64",
    "load_snips",
    "load_trec6",
]
