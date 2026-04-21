# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0

"""``dendra`` CLI — minimum-viable entry point.

Subcommands:

- ``dendra bench <benchmark>`` — run the transition-curve experiment
  for a named public intent-classification dataset and print JSON-lines
  checkpoints to stdout.

Intentionally argparse-based; no third-party CLI deps.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Optional, Sequence


_BENCHMARKS = {
    "banking77": "load_banking77",
    "clinc150": "load_clinc150",
    "hwu64": "load_hwu64",
    "atis": "load_atis",
}


def _load_bench(name: str):
    from dendra.benchmarks import loaders

    return getattr(loaders, _BENCHMARKS[name])()


def cmd_bench(args: argparse.Namespace) -> int:
    if args.benchmark not in _BENCHMARKS:
        print(
            f"unknown benchmark {args.benchmark!r}; "
            f"choose from {sorted(_BENCHMARKS)}",
            file=sys.stderr,
        )
        return 2

    from dendra.benchmarks.rules import build_reference_rule
    from dendra.ml import SklearnTextHead
    from dendra.research import run_benchmark_experiment

    ds = _load_bench(args.benchmark)
    rule = build_reference_rule(
        ds.train, seed_size=args.seed_size, keywords_per_label=args.kw_per_label,
    ).as_callable()
    head = SklearnTextHead(min_outcomes=args.min_train_for_ml)

    llm = _build_llm(args) if args.llm else None
    checkpoints = run_benchmark_experiment(
        train=ds.train,
        test=ds.test,
        rule=rule,
        ml_head=head,
        checkpoint_every=args.checkpoint_every,
        min_train_for_ml=args.min_train_for_ml,
        max_train=args.max_train,
        llm=llm,
        llm_labels=ds.labels,
        llm_test_sample_size=args.llm_test_sample,
    )

    summary = {
        "benchmark": ds.name,
        "labels": len(ds.labels),
        "train_rows": len(ds.train),
        "test_rows": len(ds.test),
        "seed_size": args.seed_size,
        "kw_per_label": args.kw_per_label,
        "checkpoint_every": args.checkpoint_every,
        "citation": ds.citation,
    }
    print(json.dumps({"kind": "summary", **summary}))
    for cp in checkpoints:
        print(json.dumps({"kind": "checkpoint", **asdict(cp)}))

    return 0


def _build_llm(args: argparse.Namespace):
    """Factory — map CLI args to an LLMClassifier instance."""
    from dendra.llm import (
        AnthropicAdapter,
        LlamafileAdapter,
        OllamaAdapter,
        OpenAIAdapter,
    )

    kind = args.llm
    if kind == "ollama":
        return OllamaAdapter(model=args.llm_model or "llama3.2:1b")
    if kind == "llamafile":
        return LlamafileAdapter(model=args.llm_model or "LLaMA_CPP")
    if kind == "openai":
        return OpenAIAdapter(model=args.llm_model or "gpt-4o-mini")
    if kind == "anthropic":
        return AnthropicAdapter(model=args.llm_model or "claude-haiku-4-5")
    raise ValueError(f"unknown llm backend {kind!r}")


def cmd_analyze(args: argparse.Namespace) -> int:
    """Scan a codebase for classification sites."""
    from dendra.analyzer import (
        analyze,
        project_savings,
        render_json,
        render_markdown,
        render_text,
    )

    report = analyze(args.path)

    if args.format == "json":
        print(render_json(report))
        return 0

    if args.format == "markdown":
        projections = project_savings(report) if args.project_savings else None
        print(render_markdown(report, projections=projections))
        return 0

    # Default: text.
    print(render_text(report))
    if args.project_savings and report.sites:
        print()
        print("Run with --format markdown for the savings projection table.")
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """Wrap a target function with @ml_switch via AST injection."""
    from pathlib import Path

    from dendra.wrap import WrapError, wrap_function

    try:
        file_path, function_name = args.target.rsplit(":", 1)
    except ValueError:
        print(
            f"target must be FILE:FUNCTION (got {args.target!r})",
            file=sys.stderr,
        )
        return 2

    path = Path(file_path)
    if not path.exists():
        print(f"file not found: {file_path}", file=sys.stderr)
        return 2

    source = path.read_text(encoding="utf-8")
    labels = None
    if args.labels:
        labels = [lbl.strip() for lbl in args.labels.split(",") if lbl.strip()]

    try:
        result = wrap_function(
            source,
            function_name,
            author=args.author,
            labels=labels,
            phase=args.phase,
            safety_critical=args.safety_critical,
        )
    except WrapError as e:
        print(f"dendra init: {e}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(result.diff(filename=file_path))
        print(
            f"\n# would modify {file_path}: "
            f"{len(result.labels)} labels "
            f"({'inferred' if result.inferred_labels else 'supplied'}), "
            f"phase={args.phase}"
            f"{', safety_critical' if args.safety_critical else ''}",
            file=sys.stderr,
        )
        return 0

    path.write_text(result.modified_source, encoding="utf-8")
    print(
        f"wrapped {function_name} in {file_path} with "
        f"{len(result.labels)} labels "
        f"({'inferred' if result.inferred_labels else 'supplied'})",
        file=sys.stderr,
    )
    return 0


def cmd_roi(args: argparse.Namespace) -> int:
    from dendra.roi import (
        ROIAssumptions,
        compute_portfolio_roi,
        format_portfolio_report,
    )
    from dendra.storage import FileStorage

    storage = FileStorage(args.storage)
    overrides = {}
    if args.engineer_cost_per_week is not None:
        overrides["engineer_cost_per_week_usd"] = args.engineer_cost_per_week
    if args.monthly_value_low is not None:
        overrides["monthly_value_per_site_low_usd"] = args.monthly_value_low
    if args.monthly_value_high is not None:
        overrides["monthly_value_per_site_high_usd"] = args.monthly_value_high
    assumptions = ROIAssumptions(**overrides) if overrides else ROIAssumptions()
    rois = compute_portfolio_roi(storage=storage, assumptions=assumptions)
    if args.json:
        import json
        from dataclasses import asdict

        print(
            json.dumps(
                {
                    "assumptions": asdict(assumptions),
                    "switches": [asdict(r) for r in rois],
                },
                indent=2,
            )
        )
    else:
        print(format_portfolio_report(rois, assumptions=assumptions))
    return 0


def cmd_plot(args: argparse.Namespace) -> int:
    from dendra.viz import load_run, plot_transition_curves

    runs = [load_run(p) for p in args.jsonl]
    plot_transition_curves(
        runs, output_path=args.output, title=args.title,
    )
    print(f"wrote {args.output}", file=sys.stderr)
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="dendra")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_bench = sub.add_parser(
        "bench",
        help="Run the transition-curve experiment on a public benchmark.",
    )
    p_bench.add_argument(
        "benchmark",
        choices=sorted(_BENCHMARKS),
        help="Benchmark ID (banking77 | clinc150 | hwu64 | atis).",
    )
    p_bench.add_argument("--seed-size", type=int, default=100,
                         help="Training examples used to construct the rule (paper §4.2).")
    p_bench.add_argument("--kw-per-label", type=int, default=5,
                         help="Keywords selected per label.")
    p_bench.add_argument("--checkpoint-every", type=int, default=250,
                         help="Outcomes between checkpoints.")
    p_bench.add_argument("--min-train-for-ml", type=int, default=100,
                         help="Smallest training count at which the ML head is fit.")
    p_bench.add_argument("--max-train", type=int, default=None,
                         help="Cap on training examples (smoke-test knob).")
    p_bench.add_argument(
        "--llm",
        choices=["ollama", "llamafile", "openai", "anthropic"],
        default=None,
        help="Enable LLM shadow evaluation with the named provider.",
    )
    p_bench.add_argument("--llm-model", default=None,
                         help="Model ID passed to the LLM provider.")
    p_bench.add_argument("--llm-test-sample", type=int, default=None,
                         help="Subsample size for LLM test evaluation (default: full test set).")
    p_bench.set_defaults(fn=cmd_bench)

    p_analyze = sub.add_parser(
        "analyze",
        help="Find classification sites in a codebase.",
    )
    p_analyze.add_argument(
        "path",
        help="Path to scan (file or directory).",
    )
    p_analyze.add_argument(
        "--format",
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format. Default: text (human-readable).",
    )
    p_analyze.add_argument(
        "--json",
        action="store_true",
        help="Shortcut for --format=json.",
    )
    p_analyze.add_argument(
        "--project-savings",
        action="store_true",
        help="Include per-site annual savings projection "
             "(uses dendra.roi default cost model).",
    )
    p_analyze.set_defaults(fn=cmd_analyze)
    # Back-compat: --json flag overrides --format.
    def _analyze_wrapper(args: argparse.Namespace) -> int:
        if args.json:
            args.format = "json"
        return cmd_analyze(args)
    p_analyze.set_defaults(fn=_analyze_wrapper)

    p_init = sub.add_parser(
        "init",
        help="Wrap a target function with @ml_switch via AST injection.",
    )
    p_init.add_argument(
        "target",
        help="FILE:FUNCTION — e.g., src/triage.py:triage_ticket",
    )
    p_init.add_argument(
        "--author",
        required=True,
        help="Principal identifier in Matrix style, e.g., @triage:support",
    )
    p_init.add_argument(
        "--labels",
        help="Comma-separated labels. Inferred from return statements if omitted.",
    )
    p_init.add_argument(
        "--phase",
        default="RULE",
        choices=[
            "RULE", "LLM_SHADOW", "LLM_PRIMARY",
            "ML_SHADOW", "ML_WITH_FALLBACK", "ML_PRIMARY",
        ],
        help="Initial phase. Default: RULE.",
    )
    p_init.add_argument(
        "--safety-critical",
        action="store_true",
        help="Set safety_critical=True (caps graduation at Phase 4).",
    )
    p_init.add_argument(
        "--dry-run",
        action="store_true",
        help="Print unified diff instead of modifying the file.",
    )
    p_init.set_defaults(fn=cmd_init)

    p_roi = sub.add_parser(
        "roi",
        help="Self-measured ROI report from outcome logs under a FileStorage root.",
    )
    p_roi.add_argument("storage", help="FileStorage base path (dir containing per-switch subdirs).")
    p_roi.add_argument("--json", action="store_true", help="Emit JSON instead of a text report.")
    p_roi.add_argument("--engineer-cost-per-week", type=float, default=None,
                       help="Override fully-loaded eng cost in USD/week.")
    p_roi.add_argument("--monthly-value-low", type=float, default=None,
                       help="Override monthly value per site (low bound).")
    p_roi.add_argument("--monthly-value-high", type=float, default=None,
                       help="Override monthly value per site (high bound).")
    p_roi.set_defaults(fn=cmd_roi)

    p_plot = sub.add_parser(
        "plot",
        help="Plot transition curves from one or more `dendra bench` JSONL files.",
    )
    p_plot.add_argument("jsonl", nargs="+",
                        help="One or more JSONL files produced by `dendra bench`.")
    p_plot.add_argument("-o", "--output", required=True,
                        help="Output image path (.png / .svg / .pdf).")
    p_plot.add_argument("--title", default="Dendra transition curves",
                        help="Figure title.")
    p_plot.set_defaults(fn=cmd_plot)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
