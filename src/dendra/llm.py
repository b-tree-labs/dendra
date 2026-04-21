# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0

"""LLM classifier protocol and optional provider adapters.

Phase 1 (LLM_SHADOW) and Phase 2 (LLM_PRIMARY) need an LLM to produce a
classification. Dendra never hard-depends on a specific provider — users
supply any object that satisfies the :class:`LLMClassifier` protocol, or
they pull in one of the optional adapters below (all behind lazy
imports so ``pip install dendra`` stays dep-free).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LLMPrediction:
    """What an LLM classifier returns for one input."""

    label: str
    confidence: float


@runtime_checkable
class LLMClassifier(Protocol):
    """Any object with a ``classify(input, labels) -> LLMPrediction``.

    ``input`` is the raw object passed to the switch (not stringified
    by Dendra — the adapter owns serialization).

    ``labels`` is the exhaustive label list declared on the switch.
    Adapters may use it to constrain the output, scaffold a prompt, or
    ignore it for zero-shot behavior.
    """

    def classify(self, input: Any, labels: Iterable[str]) -> LLMPrediction: ...


# ---------------------------------------------------------------------------
# Adapters (optional; lazy-imported)
# ---------------------------------------------------------------------------


class _BaseAdapter:
    """Shared helpers for shipped provider adapters."""

    @staticmethod
    def _render_prompt(input: Any, labels: Iterable[str]) -> str:
        label_list = ", ".join(labels)
        return (
            "Classify the following input into exactly one of these labels: "
            f"[{label_list}].\n"
            f"Input: {input!r}\n"
            "Return only the label, no extra text."
        )

    @staticmethod
    def _normalize_label(text: str, labels: Iterable[str]) -> str:
        """Best-effort match of a model output to one of ``labels``.

        Strategy: pull the first non-empty line, lowercase + strip
        punctuation, then (1) exact match, (2) whole-string-in-label
        match, (3) longest substring match. Returns the first label as
        a fallback — the caller should flag that via confidence.
        """
        label_list = list(labels)
        if not label_list:
            return text.strip()

        first_line = ""
        for line in text.splitlines():
            line = line.strip()
            if line:
                first_line = line
                break
        cleaned = first_line.strip(".?!\"'`:- ").lower()
        lower_labels = [lbl.lower() for lbl in label_list]
        if cleaned in lower_labels:
            return label_list[lower_labels.index(cleaned)]
        # Labels whose text matches the cleaned string in either direction.
        containing_cleaned = [lbl for lbl in label_list if cleaned and cleaned in lbl.lower()]
        if containing_cleaned:
            return min(containing_cleaned, key=len)
        hits = [lbl for lbl in label_list if lbl.lower() in cleaned]
        if hits:
            return max(hits, key=len)
        return label_list[0]


class OpenAIAdapter(_BaseAdapter):
    """OpenAI-compatible chat-completions classifier.

    Works against any endpoint that speaks the OpenAI Chat API (OpenAI
    itself, Together, Groq, local vLLM, LiteLLM proxy, etc.) — pass a
    custom ``base_url`` to target alternates.
    """

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.0,
    ) -> None:
        try:
            from openai import OpenAI  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "OpenAIAdapter requires the openai SDK. "
                "Install with `pip install dendra[openai]` or `pip install openai`."
            ) from e
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._temperature = temperature

    def classify(self, input: Any, labels: Iterable[str]) -> LLMPrediction:
        labels = list(labels)
        prompt = self._render_prompt(input, labels)
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self._temperature,
            logprobs=True,
            top_logprobs=1,
        )
        choice = resp.choices[0]
        raw = (choice.message.content or "").strip()
        label = self._normalize_label(raw, labels)
        confidence = _logprob_to_confidence(choice)
        return LLMPrediction(label=label, confidence=confidence)


class AnthropicAdapter(_BaseAdapter):
    """Anthropic Messages API adapter."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        max_tokens: int = 32,
    ) -> None:
        try:
            from anthropic import Anthropic  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "AnthropicAdapter requires the anthropic SDK. "
                "Install with `pip install dendra[anthropic]` or `pip install anthropic`."
            ) from e
        self._client = Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def classify(self, input: Any, labels: Iterable[str]) -> LLMPrediction:
        labels = list(labels)
        prompt = self._render_prompt(input, labels)
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(getattr(block, "text", "") for block in resp.content).strip()
        # Anthropic doesn't expose token logprobs; approximate confidence as
        # 1.0 if the returned text exactly matches one of the allowed labels,
        # else a lower bound reflecting the uncertainty.
        exact_hit = text in labels
        label = self._normalize_label(text, labels)
        confidence = 0.9 if exact_hit else 0.5
        return LLMPrediction(label=label, confidence=confidence)


class OllamaAdapter(_BaseAdapter):
    """Ollama local-LLM adapter (http://localhost:11434 by default)."""

    def __init__(
        self,
        *,
        model: str,
        host: str = "http://localhost:11434",
    ) -> None:
        try:
            import httpx  # type: ignore[import-untyped]
        except ImportError as e:
            raise ImportError(
                "OllamaAdapter requires httpx. "
                "Install with `pip install dendra[ollama]` or `pip install httpx`."
            ) from e
        self._httpx = httpx
        self._model = model
        self._host = host.rstrip("/")

    def classify(self, input: Any, labels: Iterable[str]) -> LLMPrediction:
        labels = list(labels)
        prompt = self._render_prompt(input, labels)
        r = self._httpx.post(
            f"{self._host}/api/generate",
            json={"model": self._model, "prompt": prompt, "stream": False},
            timeout=60.0,
        )
        r.raise_for_status()
        text = (r.json().get("response") or "").strip()
        exact_hit = text in labels
        label = self._normalize_label(text, labels)
        confidence = 0.85 if exact_hit else 0.5
        return LLMPrediction(label=label, confidence=confidence)


class LlamafileAdapter(OpenAIAdapter):
    """Llamafile adapter — thin wrapper over OpenAIAdapter.

    Llamafile exposes an OpenAI-compatible endpoint on localhost; point
    :class:`OpenAIAdapter` at it. This subclass fixes the base_url so
    callers don't have to remember the port.
    """

    def __init__(
        self,
        *,
        model: str = "LLaMA_CPP",
        base_url: str = "http://localhost:8080/v1",
        api_key: str = "sk-no-key-required",
        temperature: float = 0.0,
    ) -> None:
        super().__init__(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=temperature,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _logprob_to_confidence(choice: Any) -> float:
    """Best-effort probability for OpenAI-style completions.

    Uses the top token logprob when available; falls back to 0.8 if the
    provider didn't return logprobs.
    """
    try:
        import math

        content = choice.logprobs.content  # type: ignore[attr-defined]
        if not content:
            return 0.8
        # Highest-confidence first token is a reasonable proxy.
        return float(math.exp(content[0].logprob))
    except (AttributeError, IndexError, TypeError, ValueError):
        return 0.8


__all__ = [
    "AnthropicAdapter",
    "LLMClassifier",
    "LLMPrediction",
    "LlamafileAdapter",
    "OllamaAdapter",
    "OpenAIAdapter",
]
