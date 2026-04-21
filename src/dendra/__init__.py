# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0

"""Dendra — graduated-autonomy classification primitive.

Six-phase lifecycle from hand-written rule to learned classifier,
with a statistical transition gate at every phase, a safety-critical
cap that refuses construction in the highest-autonomy phase for
authorization-class decisions, a circuit breaker that reverts to the
rule on ML failure, and shadow-path isolation that keeps observational
classifiers from affecting user-visible output.

Core public API: :class:`LearnedSwitch`, :func:`ml_switch` decorator,
:class:`Phase`, :class:`SwitchConfig`, :class:`OutcomeRecord`,
:class:`FileStorage`, and the LLM/ML protocol interfaces.

Tooling (analyzer, ROI reporter, AST-based `wrap_function`, viz,
research runners) ships in submodules — import directly:
``from dendra.analyzer import analyze``, ``from dendra.roi import
compute_switch_roi``, etc.

See README.md and https://dendra.dev.
"""

__version__ = "0.2.0"

from dendra.core import (
    LearnedSwitch,
    Outcome,
    OutcomeRecord,
    Phase,
    SwitchConfig,
    SwitchResult,
    SwitchStatus,
)
from dendra.decorator import ml_switch
from dendra.llm import (
    AnthropicAdapter,
    LlamafileAdapter,
    LLMClassifier,
    LLMPrediction,
    OllamaAdapter,
    OpenAIAdapter,
)
from dendra.ml import MLHead, MLPrediction, SklearnTextHead
from dendra.storage import FileStorage, InMemoryStorage, Storage
from dendra.telemetry import (
    ListEmitter,
    NullEmitter,
    StdoutEmitter,
    TelemetryEmitter,
)

__all__ = [
    "AnthropicAdapter",
    "FileStorage",
    "InMemoryStorage",
    "LearnedSwitch",
    "ListEmitter",
    "LLMClassifier",
    "LLMPrediction",
    "LlamafileAdapter",
    "MLHead",
    "MLPrediction",
    "NullEmitter",
    "OllamaAdapter",
    "OpenAIAdapter",
    "Outcome",
    "OutcomeRecord",
    "Phase",
    "SklearnTextHead",
    "StdoutEmitter",
    "Storage",
    "SwitchConfig",
    "SwitchResult",
    "SwitchStatus",
    "TelemetryEmitter",
    "__version__",
    "ml_switch",
]
