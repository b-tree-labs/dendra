# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0

"""Dendra — graduated-autonomy classification primitive.

v0.2.0 — Phase 1 (LLM_SHADOW). See README.md.
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
    LLMClassifier,
    LLMPrediction,
    LlamafileAdapter,
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
