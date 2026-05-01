#!/usr/bin/env python3
# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0

"""Refresh landing/data/llm-prices.json from LiteLLM's pricing catalog.

LiteLLM maintains `model_prices_and_context_window.json` — the de-facto
pricing JSON the LLM ecosystem uses (LangChain, LlamaIndex, etc. all
read it). It updates multiple times per week from public provider
pricing pages. We pull from it, extract our curated provider set, and
rewrite landing/data/llm-prices.json.

Curate by editing CURATED below. Prices, model IDs, and "last_updated"
come from the upstream. Run weekly via .github/workflows/refresh-llm-prices.yml.
"""

from __future__ import annotations

import datetime as _dt
import json
import sys
import urllib.request
from pathlib import Path

LITELLM_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm/main/"
    "model_prices_and_context_window.json"
)

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = REPO_ROOT / "landing" / "data" / "llm-prices.json"

# Curated set: edit this list to add/remove providers from the calculator.
# `litellm_key` must exist in the upstream JSON with non-null
# input_cost_per_token and output_cost_per_token.
CURATED: list[dict] = [
    {
        "id": "anthropic_opus_47",
        "litellm_key": "claude-opus-4-7",
        "label": "Anthropic Claude Opus 4.7",
        "notes": "Anthropic's flagship reasoning model. Common premium classifier choice for high-stakes labels.",
    },
    {
        "id": "anthropic_sonnet_46",
        "litellm_key": "claude-sonnet-4-6",
        "label": "Anthropic Claude Sonnet 4.6",
        "notes": "Anthropic's workhorse. The most-used production classifier across the Anthropic line.",
    },
    {
        "id": "anthropic_haiku_45",
        "litellm_key": "claude-haiku-4-5",
        "label": "Anthropic Claude Haiku 4.5",
        "notes": "Anthropic's fast tier. Frequent default for high-volume classifier workloads.",
    },
    {
        "id": "openai_gpt55",
        "litellm_key": "gpt-5.5",
        "label": "OpenAI GPT-5.5",
        "notes": "OpenAI's current frontier (released 2026-04-23). Top-of-line reasoning.",
    },
    {
        "id": "openai_gpt54_mini",
        "litellm_key": "gpt-5.4-mini",
        "label": "OpenAI GPT-5.4 mini",
        "notes": "OpenAI's cheap frontier-tier. Strong classifier accuracy at a fraction of GPT-5.5's per-call cost.",
    },
    {
        "id": "google_gemini_31_pro",
        "litellm_key": "gemini/gemini-3.1-pro-preview",
        "label": "Google Gemini 3.1 Pro",
        "notes": "Google's current frontier (preview). Strong long-context for classifier prompts with retrieval.",
    },
    {
        "id": "google_gemini_3_flash",
        "litellm_key": "gemini/gemini-3-flash-preview",
        "label": "Google Gemini 3 Flash",
        "notes": "Google's cheap-and-fast frontier tier. Often the lowest cost-per-call from a frontier lab.",
    },
    {
        "id": "xai_grok_420_reasoning",
        "litellm_key": "xai/grok-4.20-0309-reasoning",
        "label": "xAI Grok 4.20 (reasoning)",
        "notes": "xAI's current reasoning-grade model. Useful when Grok is already in the stack.",
    },
    {
        "id": "deepseek_v32",
        "litellm_key": "deepseek/deepseek-v3.2",
        "label": "DeepSeek V3.2",
        "notes": "Open-weights frontier with aggressive pricing. Common cheap baseline for high-volume classifiers.",
    },
    # Local inference is not in LiteLLM's pricing catalog (no per-token
    # billing). Hand-entered: notional electricity cost on Apple Silicon.
    {
        "id": "ollama_local",
        "litellm_key": None,
        "label": "Ollama (local)",
        "model_override": "qwen3:8b or similar",
        "input_per_m_usd": 0.00,
        "output_per_m_usd": 0.00,
        "per_call_usd_override": 0.00002,
        "notes": (
            "Local inference; per-call cost is notional electricity (~$0.00002/call on "
            "Apple Silicon). Zero per-token billing; latency is the trade-off."
        ),
    },
]


def fetch_litellm() -> dict:
    req = urllib.request.Request(
        LITELLM_URL,
        headers={"User-Agent": "dendra-pricing-refresh/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 — HTTPS pinned URL
        return json.loads(resp.read().decode("utf-8"))


def build_provider(catalog: dict, entry: dict) -> dict:
    if entry["litellm_key"] is None:
        # Hand-entered (local inference).
        return {
            "id": entry["id"],
            "label": entry["label"],
            "model": entry["model_override"],
            "input_per_m_usd": entry["input_per_m_usd"],
            "output_per_m_usd": entry["output_per_m_usd"],
            "per_call_usd": entry["per_call_usd_override"],
            "notes": entry["notes"],
        }

    key = entry["litellm_key"]
    if key not in catalog:
        raise KeyError(
            f"LiteLLM catalog has no entry for {key!r}; pick a different "
            f"litellm_key for {entry['id']}"
        )

    spec = catalog[key]
    inp = spec.get("input_cost_per_token")
    out = spec.get("output_cost_per_token")
    if inp is None or out is None:
        raise ValueError(
            f"LiteLLM entry {key!r} is missing input_cost_per_token or "
            f"output_cost_per_token; cannot price this provider"
        )

    # Strip provider-prefix from key for the displayed model name.
    model_name = key.split("/", 1)[1] if "/" in key else key

    # Typical classifier prompt: 250 input + 50 output tokens.
    per_call = inp * 250 + out * 50

    return {
        "id": entry["id"],
        "label": entry["label"],
        "model": model_name,
        "input_per_m_usd": round(inp * 1_000_000, 4),
        "output_per_m_usd": round(out * 1_000_000, 4),
        "per_call_usd": round(per_call, 8),
        "notes": entry["notes"],
    }


def main() -> int:
    print(f"[update_llm_prices] fetching {LITELLM_URL}", file=sys.stderr)
    catalog = fetch_litellm()
    print(f"[update_llm_prices] {len(catalog)} models in upstream catalog", file=sys.stderr)

    providers = [build_provider(catalog, entry) for entry in CURATED]

    output = {
        "$schema": "https://dendra.run/schemas/llm-prices.v1.json",
        "last_updated": _dt.date.today().isoformat(),
        "source": {
            "name": "BerriAI/litellm model_prices_and_context_window.json",
            "url": LITELLM_URL,
            "license": "MIT (LiteLLM project)",
        },
        "typical_classifier_prompt": {
            "input_tokens": 250,
            "output_tokens": 50,
            "comment": (
                "A representative classifier call: ~250 tokens of system + input, "
                "~50 tokens of output (label + brief reasoning). Per-call cost below "
                "uses these values."
            ),
        },
        "providers": providers,
        "disclaimer": (
            "Per-call cost is the typical classifier prompt cost (250 input + 50 "
            "output tokens) at the listed input/output prices. Prices are pulled "
            "weekly from BerriAI/litellm's community-maintained catalog; verify "
            "current rates with the provider before sizing a contract."
        ),
    }

    OUTPUT.write_text(json.dumps(output, indent=2) + "\n")
    print(f"[update_llm_prices] wrote {len(providers)} providers to {OUTPUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
