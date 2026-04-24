# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0

"""Verdict sources — pluggable "where does truth come from" primitives.

A :class:`VerdictSource` decides whether a classification decision
matched ground truth. Verdicts feed the outcome log, drive gate
graduation math, and populate the audit trail.

Dendra ships with three built-in sources:

- :class:`CallableVerdictSource` — wraps any
  ``(input, label) -> Verdict`` callable. The escape hatch for
  bespoke truth oracles (downstream signals, business rules,
  reviewer decisions already on hand).
- :class:`LLMJudgeSource` — single-LLM judge. Prompts the model
  to assess whether a label is correct for an input. Guards
  against the self-judgment bias pattern called out in G-Eval,
  MT-Bench, and Arena evaluation literature: running the SAME
  LLM as classifier and as judge is a known failure mode.
- :class:`LLMCommitteeSource` — multi-LLM committee. Combines
  per-model verdicts via majority vote, unanimous agreement, or
  confidence-weighted aggregation.

Custom sources: implement the :class:`VerdictSource` protocol
(``judge(input, label) -> Verdict``) on any object. The protocol
is :func:`runtime_checkable` so ``isinstance(obj, VerdictSource)``
works without inheritance.

Every verdict is stamped with a ``source`` string
(``"llm-judge:<model>"`` / ``"llm-committee:<ids>"`` /
``"callable:<name>"``) so audit-chain filters can separate
self-reported machine verdicts from human-reviewed truth.

See ``docs/verdict-sources.md`` (roadmap) for the full matrix
of when-to-use-which, and ``examples/11_llm_judge.py`` /
``examples/12_llm_committee.py`` for wired end-to-end demos.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from typing import Any, Protocol, runtime_checkable

from dendra.core import Verdict
from dendra.models import ModelClassifier


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class VerdictSource(Protocol):
    """A pluggable source of truth for classification verdicts.

    Implementations return one of the three :class:`Verdict`
    values (``CORRECT`` / ``INCORRECT`` / ``UNKNOWN``) given the
    original input and the decision label the switch returned.

    ``source_name`` is a stable string used in audit-trail
    stamping. Two :class:`VerdictSource` instances with the same
    ``source_name`` must be interchangeable in their judge
    semantics.
    """

    source_name: str

    def judge(self, input: Any, label: Any, /) -> Verdict: ...


# ---------------------------------------------------------------------------
# CallableVerdictSource — escape hatch
# ---------------------------------------------------------------------------


class CallableVerdictSource:
    """Wrap any ``(input, label) -> Verdict`` callable as a VerdictSource.

    Use when the truth signal isn't an LLM — a downstream service's
    return code, a database lookup, a business-rule function,
    a reviewer's notebook output pre-computed as a dict lookup.
    """

    def __init__(
        self,
        fn: Callable[[Any, Any], Verdict],
        *,
        name: str = "callable",
    ) -> None:
        if not callable(fn):
            raise TypeError("fn must be callable")
        if not name:
            raise ValueError("name cannot be empty")
        self._fn = fn
        self.source_name = f"callable:{name}"

    def judge(self, input: Any, label: Any, /) -> Verdict:
        result = self._fn(input, label)
        if not isinstance(result, Verdict):
            raise TypeError(
                f"callable verdict source {self.source_name!r} must return a "
                f"Verdict; got {type(result).__name__}"
            )
        return result


# ---------------------------------------------------------------------------
# LLMJudgeSource — single-LLM judge with bias guardrails
# ---------------------------------------------------------------------------


_JUDGE_LABELS = ["correct", "incorrect", "unknown"]


def _identify_llm(llm: ModelClassifier) -> tuple[str, str]:
    """Extract a ``(class_name, model_string)`` pair for identity checks."""
    cls = type(llm).__name__
    model = str(
        getattr(llm, "_model", None)
        or getattr(llm, "model", None)
        or ""
    )
    return cls, model


def _same_llm(a: ModelClassifier, b: ModelClassifier) -> bool:
    """Best-effort identity check.

    True when ``a`` and ``b`` are literally the same object, or when
    they expose the same ``(class_name, model_string)`` pair —
    which catches "two separate OpenAIAdapter(model='gpt-4o-mini')
    instances."
    """
    if a is b:
        return True
    return _identify_llm(a) == _identify_llm(b)


class LLMJudgeSource:
    """Single-LLM judge.

    Prompts ``judge_model`` to evaluate whether ``label`` is the
    correct classification for ``input``. Returns one of
    :class:`Verdict` based on the judge's response.

    Bias guardrail
    --------------
    Using the same LLM as both classifier and judge is a
    well-documented anti-pattern — the same model tends to agree
    with its own outputs even when wrong. When
    ``guard_against_same_llm=True`` (the default), constructing
    a judge alongside a ``require_distinct_from=`` classifier
    that points at the same provider/model raises
    ``ValueError`` immediately. Pass
    ``guard_against_same_llm=False`` only if you explicitly
    accept the self-judgment bias risk and have your own mitigation.

    References: G-Eval (NAACL 2023), MT-Bench (NeurIPS 2023),
    Chatbot Arena (ICML 2024) — all report meaningful bias when
    the same LLM judges its own outputs.
    """

    def __init__(
        self,
        judge_model: ModelClassifier,
        *,
        require_distinct_from: ModelClassifier | None = None,
        guard_against_same_llm: bool = True,
        prompt_template: str | None = None,
    ) -> None:
        if not isinstance(judge_model, ModelClassifier):
            raise TypeError(
                "judge_model must satisfy the ModelClassifier protocol "
                "(classify(input, labels) -> ModelPrediction)"
            )
        if guard_against_same_llm and require_distinct_from is not None:
            if _same_llm(judge_model, require_distinct_from):
                cls, model = _identify_llm(judge_model)
                raise ValueError(
                    f"refusing to construct LLMJudgeSource: judge_model and "
                    f"require_distinct_from resolve to the same LLM "
                    f"({cls} / model={model!r}). Using the same LLM as "
                    f"classifier and judge biases verdicts toward the "
                    f"classifier's own errors — see G-Eval / MT-Bench / "
                    f"Arena literature. Pass a distinct model, or set "
                    f"guard_against_same_llm=False if you explicitly "
                    f"accept the bias risk."
                )
        self._judge = judge_model
        cls, model = _identify_llm(judge_model)
        tag = model or cls
        self.source_name = f"llm-judge:{tag}"
        self._prompt_template = prompt_template or _DEFAULT_JUDGE_PROMPT

    def judge(self, input: Any, label: Any, /) -> Verdict:
        prompt = self._prompt_template.format(input=input, label=label)
        try:
            pred = self._judge.classify(prompt, _JUDGE_LABELS)
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException:
            # A judge-side outage must not break the caller's audit
            # loop. Surface UNKNOWN so the record is recoverable but
            # the downstream gate math correctly ignores unverdicted
            # rows.
            return Verdict.UNKNOWN
        text = str(pred.label).strip().lower()
        if text == "correct":
            return Verdict.CORRECT
        if text == "incorrect":
            return Verdict.INCORRECT
        return Verdict.UNKNOWN


_DEFAULT_JUDGE_PROMPT = (
    "You are evaluating whether a classifier's output is correct.\n"
    "Input: {input!r}\n"
    "Classifier's label: {label!r}\n"
    "Is the label correct for this input? Answer with exactly one "
    'of: "correct", "incorrect", or "unknown" (when the input is '
    "ambiguous or you don't have enough context).\n"
    "Answer:"
)


# ---------------------------------------------------------------------------
# LLMCommitteeSource — multi-judge aggregation
# ---------------------------------------------------------------------------


_COMMITTEE_MODES = ("majority", "unanimous", "confidence_weighted")


class LLMCommitteeSource:
    """Aggregate verdicts across multiple LLM judges.

    Modes
    -----
    - ``"majority"`` — the most-voted verdict wins. Ties go to
      ``UNKNOWN``. Stable on small committees (3, 5, 7 judges).
    - ``"unanimous"`` — all judges must agree on a non-UNKNOWN
      verdict; any disagreement → UNKNOWN. Use when false positives
      are expensive (medical diagnosis, irreversible actions).
    - ``"confidence_weighted"`` — future extension; for v1 this
      falls through to majority. Reserved so callers can pin
      the enum value today.

    Bias guardrail
    --------------
    Every pair of judges is checked against the
    ``require_distinct_from`` classifier (if supplied) using the
    same identity heuristic as :class:`LLMJudgeSource`. A
    committee of clones of the production classifier is a
    degenerate case that the guardrail refuses at construction.
    """

    def __init__(
        self,
        judges: Sequence[ModelClassifier],
        *,
        mode: str = "majority",
        require_distinct_from: ModelClassifier | None = None,
        guard_against_same_llm: bool = True,
        prompt_template: str | None = None,
    ) -> None:
        judge_list = list(judges)
        if len(judge_list) < 2:
            raise ValueError(
                "LLMCommitteeSource requires at least 2 judges; "
                f"got {len(judge_list)}"
            )
        if mode not in _COMMITTEE_MODES:
            raise ValueError(
                f"mode must be one of {_COMMITTEE_MODES}; got {mode!r}"
            )
        for j in judge_list:
            if not isinstance(j, ModelClassifier):
                raise TypeError(
                    "every judge must satisfy the ModelClassifier protocol"
                )
        if guard_against_same_llm and require_distinct_from is not None:
            for j in judge_list:
                if _same_llm(j, require_distinct_from):
                    cls, model = _identify_llm(j)
                    raise ValueError(
                        f"refusing to construct LLMCommitteeSource: at "
                        f"least one judge resolves to the same LLM as "
                        f"require_distinct_from ({cls} / model={model!r}). "
                        f"See LLMJudgeSource for the bias-risk rationale."
                    )
        self._judges = judge_list
        self._mode = mode
        self._template = prompt_template or _DEFAULT_JUDGE_PROMPT
        ids = [_identify_llm(j)[1] or _identify_llm(j)[0] for j in judge_list]
        self.source_name = f"llm-committee:{'|'.join(ids)}({mode})"

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def judges(self) -> list[ModelClassifier]:
        return list(self._judges)

    def judge(self, input: Any, label: Any, /) -> Verdict:
        verdicts: list[Verdict] = []
        prompt = self._template.format(input=input, label=label)
        for j in self._judges:
            try:
                pred = j.classify(prompt, _JUDGE_LABELS)
            except (KeyboardInterrupt, SystemExit):
                raise
            except BaseException:
                verdicts.append(Verdict.UNKNOWN)
                continue
            text = str(pred.label).strip().lower()
            if text == "correct":
                verdicts.append(Verdict.CORRECT)
            elif text == "incorrect":
                verdicts.append(Verdict.INCORRECT)
            else:
                verdicts.append(Verdict.UNKNOWN)

        if self._mode == "unanimous":
            first = verdicts[0]
            if first is Verdict.UNKNOWN:
                return Verdict.UNKNOWN
            return first if all(v is first for v in verdicts) else Verdict.UNKNOWN

        # Majority (also the confidence_weighted fallthrough for v1).
        counts: dict[Verdict, int] = {}
        for v in verdicts:
            counts[v] = counts.get(v, 0) + 1
        # Drop UNKNOWN as a tiebreaker candidate unless it's the only option.
        contenders = {k: v for k, v in counts.items() if k is not Verdict.UNKNOWN}
        if not contenders:
            return Verdict.UNKNOWN
        max_votes = max(contenders.values())
        winners = [k for k, v in contenders.items() if v == max_votes]
        if len(winners) != 1:
            return Verdict.UNKNOWN
        return winners[0]


# ---------------------------------------------------------------------------
# HumanReviewerSource — queue-backed manual labeling
# ---------------------------------------------------------------------------


import queue as _queue_mod


class HumanReviewerSource:
    """Queue-backed verdict source for human reviewers.

    Every ``judge(input, label)`` call pushes a request onto a
    pending queue and then **blocks** until a matching verdict
    appears on a verdicts queue. The reviewer tool (a web UI, a
    Slack bot, a CLI) dequeues from ``pending``, presents the row
    to a human, and puts the resulting verdict back on
    ``verdicts``. A timeout on the blocking wait keeps the switch
    from stalling indefinitely when no reviewer is on shift — on
    timeout the verdict is ``UNKNOWN``.

    For v1 the queues are stdlib ``queue.Queue``. Subclass and
    override :meth:`_push` / :meth:`_pop_verdict` to route through
    Redis, SQS, Kafka, or a reviewer-tool's webhook.

    Intended for ``bulk_record_verdicts_from_source`` cold-start
    pipelines (seed the log with reviewer-labeled rows) and for
    ``export_for_review`` / ``apply_reviews`` periodic-drain
    workflows. Also works inline on ``classify`` for small-volume,
    human-in-the-loop production paths.
    """

    def __init__(
        self,
        *,
        pending: _queue_mod.Queue | None = None,
        verdicts: _queue_mod.Queue | None = None,
        timeout: float = 30.0,
        name: str = "default",
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self._pending = pending if pending is not None else _queue_mod.Queue()
        self._verdicts = verdicts if verdicts is not None else _queue_mod.Queue()
        self._timeout = timeout
        self.source_name = f"human-reviewer:{name}"

    @property
    def pending(self) -> _queue_mod.Queue:
        """Queue that reviewer tools consume from. Each item is a
        ``(input, label)`` tuple."""
        return self._pending

    @property
    def verdicts(self) -> _queue_mod.Queue:
        """Queue that reviewer tools produce onto. Each item is a
        :class:`dendra.core.Verdict`."""
        return self._verdicts

    def _push(self, input: Any, label: Any) -> None:
        self._pending.put((input, label))

    def _pop_verdict(self) -> Verdict:
        try:
            return self._verdicts.get(timeout=self._timeout)
        except _queue_mod.Empty:
            return Verdict.UNKNOWN

    def judge(self, input: Any, label: Any, /) -> Verdict:
        self._push(input, label)
        v = self._pop_verdict()
        if isinstance(v, Verdict):
            return v
        # Allow reviewer-tool implementations to put str values for
        # convenience (common when coming off a JSON queue).
        if isinstance(v, str):
            try:
                return Verdict(v)
            except ValueError:
                return Verdict.UNKNOWN
        return Verdict.UNKNOWN


# ---------------------------------------------------------------------------
# WebhookVerdictSource — poll an HTTP endpoint for verdicts
# ---------------------------------------------------------------------------


class WebhookVerdictSource:
    """Poll an HTTP endpoint that returns verdicts for pending inputs.

    The pattern: your external system (ticketing tool, fraud
    detector, downstream consumer) can report outcomes but
    doesn't push them — you pull. Each ``judge(input, label)``
    call performs a POST to ``endpoint`` with a JSON body
    ``{"input": <input>, "label": <label>}`` and parses a response
    body ``{"outcome": "correct"|"incorrect"|"unknown"}``.

    Failure modes handled:

    - HTTP non-2xx, connection error, timeout → ``Verdict.UNKNOWN``
      (external outage must not break the caller's audit loop).
    - Malformed JSON or missing ``outcome`` key → ``Verdict.UNKNOWN``.
    - ``outcome`` value not matching a :class:`Verdict` → ``Verdict.UNKNOWN``.

    Requires :mod:`httpx`. Install with ``pip install dendra[ollama]``
    (same optional dep as the Ollama adapter) or ``pip install httpx``.

    Skeleton: v1 ships the blocking HTTP call. An async peer lands
    in Session 7. For webhook-push semantics (the external system
    POSTs to you), accept the push in your own HTTP route and call
    ``switch.record_verdict`` or ``switch.apply_reviews`` directly.
    """

    def __init__(
        self,
        endpoint: str,
        *,
        timeout: float = 10.0,
        headers: dict[str, str] | None = None,
        auth: tuple[str, str] | None = None,
        name: str | None = None,
    ) -> None:
        try:
            import httpx  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "WebhookVerdictSource requires httpx. "
                "Install with `pip install dendra[ollama]` (shares the "
                "Ollama adapter's optional dep) or `pip install httpx`."
            ) from e
        if not endpoint:
            raise ValueError("endpoint must be a non-empty URL")
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self._httpx = httpx
        self._endpoint = endpoint
        self._timeout = timeout
        self._headers = headers or {}
        self._auth = auth
        tag = name if name is not None else endpoint
        self.source_name = f"webhook:{tag}"

    def judge(self, input: Any, label: Any, /) -> Verdict:
        try:
            r = self._httpx.post(
                self._endpoint,
                json={"input": input, "label": label},
                headers=self._headers,
                auth=self._auth,
                timeout=self._timeout,
            )
            r.raise_for_status()
            data = r.json()
        except (KeyboardInterrupt, SystemExit):
            raise
        except BaseException:
            return Verdict.UNKNOWN
        outcome = data.get("outcome") if isinstance(data, dict) else None
        if not isinstance(outcome, str):
            return Verdict.UNKNOWN
        try:
            return Verdict(outcome)
        except ValueError:
            return Verdict.UNKNOWN


__all__ = [
    "CallableVerdictSource",
    "HumanReviewerSource",
    "LLMCommitteeSource",
    "LLMJudgeSource",
    "VerdictSource",
    "WebhookVerdictSource",
]
