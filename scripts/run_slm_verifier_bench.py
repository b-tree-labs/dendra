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

Output: docs/working/slm-verifier-benchmark.md and a JSON dump
under docs/working/benchmarks/slm-verifier-bench.json.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from dendra import LLMJudgeSource, OllamaAdapter, Verdict


# Test corpus — 30 pairs, 50/50 correct/incorrect.
# Each pair is (input, classifier_label, ground_truth_correct).
_CORPUS = [
    # bug — correct classifications (should judge "correct")
    ("app crashes on login", "bug", True),
    ("login screen throws an error", "bug", True),
    ("payment page broken after deploy", "bug", True),
    ("checkout 500s on submit", "bug", True),
    ("data export hangs forever", "bug", True),
    # bug — incorrect classifications (should judge "incorrect")
    ("can you add dark mode?", "bug", False),
    ("how do I reset my password?", "bug", False),
    ("please support keyboard shortcuts", "bug", False),
    ("billing question about Q3 invoice", "bug", False),
    ("documentation request for the SDK", "bug", False),
    # feature_request — correct
    ("add SAML support", "feature_request", True),
    ("CSV export for reports", "feature_request", True),
    ("dark mode for the dashboard", "feature_request", True),
    ("bulk-action UI for the inbox", "feature_request", True),
    ("keyboard shortcuts for navigation", "feature_request", True),
    # feature_request — incorrect
    ("application crashes when scrolling", "feature_request", False),
    ("error 500 on dashboard load", "feature_request", False),
    ("how does pricing work?", "feature_request", False),
    ("payment failed for unknown reason", "feature_request", False),
    ("when do you support OAuth?", "feature_request", False),
    # question — correct
    ("how do I export my data?", "question", True),
    ("when do you support OAuth?", "question", True),
    ("is dark mode planned?", "question", True),
    ("how does the McNemar gate work?", "question", True),
    ("what's the latency overhead?", "question", True),
    # question — incorrect
    ("the app crashes constantly", "question", False),
    ("please add SAML", "question", False),
    ("checkout error on payment", "question", False),
    ("add CSV export", "question", False),
    ("login button is broken", "question", False),
]


def _bench_model(model_name: str, ollama_host: str = "http://localhost:11434") -> dict:
    """Run the full corpus through one Ollama-hosted SLM."""
    adapter = OllamaAdapter(model=model_name, host=ollama_host)
    judge = LLMJudgeSource(adapter)

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

    score = accuracy_on_judged * format_rate

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
    }


def main() -> None:
    candidates = [
        "qwen2.5:0.5b",      # Tiniest — sanity check
        "llama3.2:1b",       # Current candidate default
        "gemma2:2b",         # Larger, often-stronger-on-judgment
    ]

    results = []
    for m in candidates:
        try:
            result = _bench_model(m)
            results.append(result)
        except Exception as e:
            print(f"\n!!! {m} failed: {type(e).__name__}: {e}")
            results.append({"model": m, "error": str(e)})

    # Persist machine-readable + human-readable.
    repo_root = Path(__file__).parent.parent
    out_dir = repo_root / "docs" / "working" / "benchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "slm-verifier-bench.json"
    json_path.write_text(json.dumps(results, indent=2))
    print(f"\n=== summary ===")
    print(f"wrote {json_path}")

    # Pick the recommended default.
    valid = [r for r in results if "error" not in r and r["composite_score"] > 0]
    if valid:
        best = max(valid, key=lambda r: r["composite_score"])
        print(f"\nrecommended default: {best['model']}")
        print(f"  format-compliance × accuracy = {best['composite_score']:.3f}")


if __name__ == "__main__":
    main()
