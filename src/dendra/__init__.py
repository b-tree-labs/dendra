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
:class:`Phase`, :class:`SwitchConfig`, :class:`ClassificationRecord`,
:class:`FileStorage`, and the language model/ML protocol interfaces.

Tooling (analyzer, ROI reporter, AST-based `wrap_function`, viz,
research runners) ships in submodules — import directly:
``from dendra.analyzer import analyze``, ``from dendra.roi import
compute_switch_roi``, etc.

See README.md and https://dendra.dev.
"""

__version__ = "1.0.0rc1"

from dendra.autoresearch import (
    CandidateHarness,
    CandidateReport,
    Tournament,
    TournamentReport,
)
from dendra.core import (
    BulkVerdict,
    BulkVerdictSummary,
    ClassificationRecord,
    ClassificationResult,
    Label,
    LearnedSwitch,
    Phase,
    SwitchConfig,
    SwitchStatus,
    Verdict,
)
from dendra.decorator import ml_switch
from dendra.gates import (
    AccuracyMarginGate,
    CompositeGate,
    Gate,
    GateDecision,
    ManualGate,
    McNemarGate,
    MinVolumeGate,
    next_phase,
    prev_phase,
)
from dendra.ml import (
    ImagePixelLogRegHead,
    MLHead,
    MLHeadFactory,
    MLPrediction,
    SklearnTextHead,
    TfidfGradientBoostingHead,
    TfidfHeadBase,
    TfidfLinearSVCHead,
    TfidfMultinomialNBHead,
    available_ml_heads,
    make_ml_head,
    register_ml_head,
)
from dendra.ml_strategy import (
    CardinalityMLHeadStrategy,
    FixedMLHeadStrategy,
    MLHeadStrategy,
)
from dendra.models import (
    AnthropicAdapter,
    AnthropicAsyncAdapter,
    LlamafileAdapter,
    LlamafileAsyncAdapter,
    ModelClassifier,
    ModelPrediction,
    OllamaAdapter,
    OllamaAsyncAdapter,
    OpenAIAdapter,
    OpenAIAsyncAdapter,
)
from dendra.storage import (
    BoundedInMemoryStorage,
    FileStorage,
    InMemoryStorage,
    ResilientStorage,
    SqliteStorage,
    Storage,
    StorageBase,
    deserialize_record,
    flock_supported,
    serialize_record,
)
from dendra.switch_class import Switch
from dendra.telemetry import (
    ListEmitter,
    NullEmitter,
    StdoutEmitter,
    TelemetryEmitter,
)
from dendra.verdicts import (
    CallableVerdictSource,
    HumanReviewerSource,
    JudgeCommittee,
    JudgeSource,
    NoVerifierAvailableError,
    VerdictSource,
    WebhookVerdictSource,
    default_verifier,
)

__all__ = [
    "AccuracyMarginGate",
    "AnthropicAdapter",
    "AnthropicAsyncAdapter",
    "BoundedInMemoryStorage",
    "BulkVerdict",
    "BulkVerdictSummary",
    "CandidateHarness",
    "CandidateReport",
    "CardinalityMLHeadStrategy",
    "CompositeGate",
    "ClassificationRecord",
    "ClassificationResult",
    "FileStorage",
    "FixedMLHeadStrategy",
    "Gate",
    "GateDecision",
    "ImagePixelLogRegHead",
    "InMemoryStorage",
    "Label",
    "LearnedSwitch",
    "ListEmitter",
    "LlamafileAdapter",
    "LlamafileAsyncAdapter",
    "MLHead",
    "MLHeadFactory",
    "MLHeadStrategy",
    "MLPrediction",
    "ManualGate",
    "McNemarGate",
    "MinVolumeGate",
    "ModelClassifier",
    "ModelPrediction",
    "NullEmitter",
    "OllamaAdapter",
    "OllamaAsyncAdapter",
    "OpenAIAdapter",
    "OpenAIAsyncAdapter",
    "Phase",
    "ResilientStorage",
    "SklearnTextHead",
    "SqliteStorage",
    "TfidfGradientBoostingHead",
    "TfidfHeadBase",
    "TfidfLinearSVCHead",
    "TfidfMultinomialNBHead",
    "StdoutEmitter",
    "Storage",
    "StorageBase",
    "Switch",
    "SwitchConfig",
    "SwitchStatus",
    "CallableVerdictSource",
    "HumanReviewerSource",
    "JudgeCommittee",
    "JudgeSource",
    "TelemetryEmitter",
    "Tournament",
    "TournamentReport",
    "Verdict",
    "VerdictSource",
    "NoVerifierAvailableError",
    "WebhookVerdictSource",
    "__version__",
    "available_ml_heads",
    "default_verifier",
    "deserialize_record",
    "flock_supported",
    "make_ml_head",
    "ml_switch",
    "next_phase",
    "prev_phase",
    "register_ml_head",
    "serialize_record",
]
