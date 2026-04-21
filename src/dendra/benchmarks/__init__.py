# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0

"""Public intent-classification benchmark loaders.

Requires the optional ``datasets`` dependency: ``pip install dendra[bench]``.
"""

from dendra.benchmarks.loaders import (
    BenchmarkDataset,
    load_atis,
    load_banking77,
    load_clinc150,
    load_hwu64,
)

__all__ = [
    "BenchmarkDataset",
    "load_atis",
    "load_banking77",
    "load_clinc150",
    "load_hwu64",
]
