#!/usr/bin/env python3
# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0
"""SLM verifier benchmark — pick the shipped default for default_verifier().

Test scenario: simulated classification pairs (input, classifier_label).
Half are correct (label matches ground truth), half intentionally wrong
(injected mistakes). The judge LLM sees each pair and is asked to
return "correct" / "incorrect" / "unknown."

For each candidate SLM we measure:
- Accuracy: % of pairs where the judge agreed with ground truth
- Format-compliance rate: % of judgments that parsed cleanly
- p50 / p99 latency per judgment (ms)

Output: a JSON dump under docs/benchmarks/slm-verifier-bench.json.
Update docs/benchmarks/slm-verifier-results.md by hand from the
new JSON.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from dendra import (
    JudgeSource,
    LlamafileAdapter,
    OllamaAdapter,
    Verdict,
)

# Test corpus — 102 pairs, 50/50 correct/incorrect, balanced across labels.
# Each pair is (input, classifier_label, ground_truth_correct).
# Expanded from n=30 to n=102 in 2026-04 to reduce variance below 5pp on
# format-rate and accuracy-on-judged metrics.
_CORPUS = [
    # ---------- bug — correct classifications (judge: "correct") ----------
    ("app crashes on login", "bug", True),
    ("login screen throws an error", "bug", True),
    ("payment page broken after deploy", "bug", True),
    ("checkout 500s on submit", "bug", True),
    ("data export hangs forever", "bug", True),
    ("memory leak after recent upgrade", "bug", True),
    ("page freezes when scrolling long tables", "bug", True),
    ("audio output distorted on Windows", "bug", True),
    ("PDF download produces empty file", "bug", True),
    ("session ends unexpectedly mid-task", "bug", True),
    ("OAuth callback returns 500 error", "bug", True),
    ("data sync stuck for two hours", "bug", True),
    ("image upload fails silently after 5MB", "bug", True),
    ("forms reject valid email addresses", "bug", True),
    ("calendar widget broke after update", "bug", True),
    ("navigation menu disappears on resize", "bug", True),
    ("mobile app crashes on iOS 17", "bug", True),
    # ---------- bug — incorrect classifications (judge: "incorrect") -------
    ("can you add dark mode?", "bug", False),
    ("how do I reset my password?", "bug", False),
    ("please support keyboard shortcuts", "bug", False),
    ("billing question about Q3 invoice", "bug", False),
    ("documentation request for the SDK", "bug", False),
    ("where can I find the changelog?", "bug", False),
    ("can you add real-time collaboration?", "bug", False),
    ("what's your refund policy?", "bug", False),
    ("please support custom domains", "bug", False),
    ("love the new color scheme", "bug", False),
    ("is there a CLI version?", "bug", False),
    ("would be great to have analytics", "bug", False),
    ("could the docs include video tutorials?", "bug", False),
    ("how do I invite team members?", "bug", False),
    ("thanks for the latest release", "bug", False),
    ("feature suggestion: dark sidebar", "bug", False),
    ("do you offer educational discounts?", "bug", False),
    # ---------- feature_request — correct ---------------------------------
    ("add SAML support", "feature_request", True),
    ("CSV export for reports", "feature_request", True),
    ("dark mode for the dashboard", "feature_request", True),
    ("bulk-action UI for the inbox", "feature_request", True),
    ("keyboard shortcuts for navigation", "feature_request", True),
    ("bulk-import contacts from CSV", "feature_request", True),
    ("two-factor auth via authenticator apps", "feature_request", True),
    ("custom themes for workspaces", "feature_request", True),
    ("audit log export to SIEM", "feature_request", True),
    ("integration with linear.app", "feature_request", True),
    ("mobile push notifications", "feature_request", True),
    ("scheduled reports via email", "feature_request", True),
    ("tag-based filtering on lists", "feature_request", True),
    ("real-time collaboration on docs", "feature_request", True),
    ("voice commands for navigation", "feature_request", True),
    ("workspace-level role permissions", "feature_request", True),
    ("calendar view for scheduled tasks", "feature_request", True),
    # ---------- feature_request — incorrect -------------------------------
    ("application crashes when scrolling", "feature_request", False),
    ("error 500 on dashboard load", "feature_request", False),
    ("how does pricing work?", "feature_request", False),
    ("payment failed for unknown reason", "feature_request", False),
    ("checkout returns 404 every time", "feature_request", False),
    ("session token expires too fast", "feature_request", False),
    ("search returns wrong results", "feature_request", False),
    ("is there a free tier?", "feature_request", False),
    ("documentation is unclear on setup", "feature_request", False),
    ("what's your uptime SLA?", "feature_request", False),
    ("page loads incomplete sometimes", "feature_request", False),
    ("rendering glitch on dashboard", "feature_request", False),
    ("data sync hangs indefinitely", "feature_request", False),
    ("how do I reset my password?", "feature_request", False),
    ("memory usage spikes randomly", "feature_request", False),
    ("API returns 502 intermittently", "feature_request", False),
    ("what's the rate limit on the api?", "feature_request", False),
    # ---------- question — correct ----------------------------------------
    ("how do I export my data?", "question", True),
    ("when do you support OAuth?", "question", True),
    ("is dark mode planned?", "question", True),
    ("how does the gate work?", "question", True),
    ("what's the latency overhead?", "question", True),
    ("how do I change my plan?", "question", True),
    ("what's the API rate limit?", "question", True),
    ("can you explain the pricing model?", "question", True),
    ("is there a demo I can watch?", "question", True),
    ("does this work with our SSO provider?", "question", True),
    ("how do I export historical data?", "question", True),
    ("what regions do you support?", "question", True),
    ("can multiple admins approve actions?", "question", True),
    ("is data encrypted at rest?", "question", True),
    ("do you have a status page?", "question", True),
    ("how is billing prorated?", "question", True),
    ("what's the difference between roles?", "question", True),
    # ---------- question — incorrect --------------------------------------
    ("the app crashes constantly", "question", False),
    ("please add SAML", "question", False),
    ("checkout error on payment", "question", False),
    ("add CSV export", "question", False),
    ("login button is broken", "question", False),
    ("screen flickers on Linux laptops", "question", False),
    ("please add Slack integration", "question", False),
    ("memory issue after long sessions", "question", False),
    ("would love bulk-edit support", "question", False),
    ("drag-and-drop is broken", "question", False),
    ("charts don't render correctly", "question", False),
    ("CSV import is buggy", "question", False),
    ("support custom report templates", "question", False),
    ("audit log export feature request", "question", False),
    ("table sort fails for date columns", "question", False),
    ("add filtering by team", "question", False),
    ("console errors during save", "question", False),
]


def _bench_model(
    model_name: str,
    *,
    backend: str = "ollama",
    ollama_host: str = "http://localhost:11434",
    llamafile_url: str = "http://localhost:8080/v1",
) -> dict:
    """Run the full corpus through one model.

    Supported backends:

    - ``"ollama"`` — routes via :class:`OllamaAdapter` to the
      Ollama daemon (default: ``localhost:11434``).
    - ``"llamafile"`` — routes via :class:`LlamafileAdapter` to
      an OpenAI-compatible llamafile server (which is also what
      Axiom's bundled local stack serves).
    - ``"openai"`` — routes via OpenAI's API. Skipped (returns a
      sentinel error row) when ``OPENAI_API_KEY`` is unset.
    - ``"anthropic"`` — routes via Anthropic's API. Skipped when
      ``ANTHROPIC_API_KEY`` is unset.
    """
    if backend == "ollama":
        adapter = OllamaAdapter(model=model_name, host=ollama_host)
    elif backend == "llamafile":
        adapter = LlamafileAdapter(model=model_name, base_url=llamafile_url)
    elif backend == "openai":
        if not os.environ.get("OPENAI_API_KEY"):
            return {
                "model": model_name,
                "backend": backend,
                "error": "OPENAI_API_KEY not set; cloud row skipped",
            }
        from dendra import OpenAIAdapter

        adapter = OpenAIAdapter(model=model_name)
    elif backend == "anthropic":
        if not os.environ.get("ANTHROPIC_API_KEY"):
            return {
                "model": model_name,
                "backend": backend,
                "error": "ANTHROPIC_API_KEY not set; cloud row skipped",
            }
        from dendra import AnthropicAdapter

        adapter = AnthropicAdapter(model=model_name)
    else:
        raise ValueError(f"unknown backend: {backend!r}")
    judge = JudgeSource(adapter)

    samples = []
    correct_count = 0
    format_compliant = 0
    parse_failures = 0

    print(f"\n=== {model_name} ===")
    for input_text, label, ground_truth in _CORPUS:
        t0 = time.perf_counter()
        try:
            verdict = judge.judge(input_text, label)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            samples.append(elapsed_ms)

            # Format compliance: did the judge return CORRECT or
            # INCORRECT? UNKNOWN counts as a non-decision (which
            # often means parse failure).
            if verdict in (Verdict.CORRECT, Verdict.INCORRECT):
                format_compliant += 1
            else:
                parse_failures += 1
                continue

            # Accuracy: did the judge match ground truth?
            judge_says_correct = verdict is Verdict.CORRECT
            if judge_says_correct == ground_truth:
                correct_count += 1
        except Exception as e:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            samples.append(elapsed_ms)
            parse_failures += 1
            print(f"  [!] {input_text!r} → ERROR: {type(e).__name__}: {e}")

    samples.sort()
    n = len(samples)
    p50 = samples[n // 2] if n else 0.0
    p99 = samples[int(n * 0.99)] if n else 0.0

    n_total = len(_CORPUS)
    n_judged = format_compliant
    n_correct = correct_count

    accuracy_on_judged = n_correct / n_judged if n_judged else 0.0
    accuracy_overall = n_correct / n_total
    format_rate = n_judged / n_total

    # Multiple composite scoring formulas — see
    # docs/benchmarks/slm-verifier-results.md for the rationale.
    # We expose all of them so reviewers can argue with the
    # ranking on data, not on choice of formula.
    score_mult = format_rate * accuracy_on_judged
    score_format_weighted = (format_rate**2) * accuracy_on_judged
    score_accuracy_weighted = format_rate * (accuracy_on_judged**2)
    # "Above chance" — penalises near-50% accuracy (pure noise) hard.
    # Maps 50% acc → 0 contribution, 100% acc → full format_rate.
    above_chance = max(0.0, 2 * accuracy_on_judged - 1)
    score_above_chance = format_rate * above_chance
    # Backwards-compat alias used by the recommendation block below.
    score = score_mult

    print(f"  format-compliance: {n_judged}/{n_total} ({format_rate:.1%})")
    print(f"  accuracy on judged: {n_correct}/{n_judged} ({accuracy_on_judged:.1%})")
    print(f"  accuracy overall:   {n_correct}/{n_total} ({accuracy_overall:.1%})")
    print(f"  latency: p50={p50:.0f}ms  p99={p99:.0f}ms")
    print(f"  composite score (acc × format): {score:.3f}")

    return {
        "model": model_name,
        "n_total": n_total,
        "n_judged": n_judged,
        "n_correct": n_correct,
        "n_parse_failures": parse_failures,
        "format_rate": format_rate,
        "accuracy_on_judged": accuracy_on_judged,
        "accuracy_overall": accuracy_overall,
        "p50_ms": p50,
        "p99_ms": p99,
        "composite_score": score,
        "score_multiplicative": score_mult,
        "score_format_weighted": score_format_weighted,
        "score_accuracy_weighted": score_accuracy_weighted,
        "score_above_chance": score_above_chance,
    }


def main() -> None:
    # (model, backend) — backend="ollama" hits localhost:11434;
    # backend="llamafile" hits localhost:8080 (Axiom's bundled Bonsai
    # serves over the same OpenAI-compatible llamafile API).
    candidates = [
        # --- prior shipped-default candidates --------------------------------
        ("qwen2.5:0.5b", "ollama"),  # ~400 MB — floor sanity check
        ("llama3.2:1b", "ollama"),  # 1.3 GB
        ("gemma2:2b", "ollama"),  # 1.6 GB
        ("llama3.2:3b", "ollama"),  # 2.0 GB — current shipped default
        # On this machine, port 8080 is raw llamafile (Axiom's HTTP wrapper
        # at port 8766 is not running). When deployed with the full Axiom
        # stack, port 8080 hits llamafile-direct and port 8766 hits the
        # pipeline+RAG-wrapped endpoint. For raw model quality, bench port
        # 8080. For "Path C user experience," bench port 8766.
        ("bonsai-1.7b.gguf", "llamafile"),  # ~1.7 GB — Axiom's bundled default (raw)
        # --- new contenders (Apr 2026) ---------------------------------------
        ("qwen2.5:1.5b", "ollama"),  # ~1.0 GB
        ("qwen2.5:3b", "ollama"),  # ~2.0 GB — direct llama3.2:3b rival
        ("qwen2.5:7b", "ollama"),  # ~4.7 GB — capacity reference
        ("deepseek-r1:1.5b", "ollama"),  # ~1.0 GB — DeepSeek-R1 distill
        ("deepseek-r1:7b", "ollama"),  # ~4.7 GB — DeepSeek-R1 distill
        ("phi3.5:3.8b", "ollama"),  # ~2.2 GB — Microsoft Phi-3.5
        # --- cloud reference rows --------------------------------------------
        # Skipped automatically when the corresponding API key isn't set;
        # otherwise serve as upper-bound references for "what would a
        # frontier verifier give us?"
        ("gpt-4o-mini", "openai"),
        ("gpt-4o", "openai"),
        ("claude-haiku-4-5", "anthropic"),
        ("claude-sonnet-4-6", "anthropic"),
    ]

    results = []
    for model_name, backend in candidates:
        try:
            result = _bench_model(model_name, backend=backend)
            result["backend"] = backend
            results.append(result)
        except Exception as e:
            print(f"\n!!! {model_name} ({backend}) failed: {type(e).__name__}: {e}")
            results.append({"model": model_name, "backend": backend, "error": str(e)})

    # Persist machine-readable + human-readable.
    repo_root = Path(__file__).parent.parent
    out_dir = repo_root / "docs" / "benchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "slm-verifier-bench.json"
    json_path.write_text(json.dumps(results, indent=2))
    print("\n=== summary ===")
    print(f"wrote {json_path}")

    # Per-formula winners. Four candidate scoring formulas; print the
    # winner each picks. If they all agree, ship that. If they diverge,
    # the divergence itself is the finding — see
    # docs/benchmarks/slm-verifier-results.md §"Why above-chance, not
    # multiplicative" for the analysis. Above-chance is what we ship on.
    valid = [r for r in results if "error" not in r]
    if not valid:
        print("\nno valid results.")
        return

    formulas = [
        ("multiplicative", "score_multiplicative"),
        ("format-weighted", "score_format_weighted"),
        ("accuracy-weighted", "score_accuracy_weighted"),
        ("above-chance", "score_above_chance"),  # the picker we ship on
    ]
    print("\nper-formula winners:")
    winners_by_formula = {}
    for label, key in formulas:
        ranked = sorted(valid, key=lambda r: -r.get(key, 0.0))
        top = ranked[0]
        winners_by_formula[label] = top["model"]
        print(f"  {label:18s} -> {top['model']:24s} (score={top.get(key, 0.0):.3f})")

    distinct = set(winners_by_formula.values())
    if len(distinct) == 1:
        print(f"\nall four formulas agree: ship {distinct.pop()}")
    else:
        print(f"\nformulas diverge: {sorted(distinct)}")
        above_chance_pick = winners_by_formula["above-chance"]
        print(f"shipped default uses above-chance formula: {above_chance_pick}")
        print("(see docs/benchmarks/slm-verifier-results.md for the rationale)")


if __name__ == "__main__":
    main()
