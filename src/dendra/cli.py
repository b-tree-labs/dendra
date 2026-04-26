# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: LicenseRef-BSL-1.1
#
# Licensed under the Business Source License 1.1 (the "License").
# You may not use this file except in compliance with the License.
# You may obtain a copy of the License at LICENSE-BSL in the
# repository root, or at https://mariadb.com/bsl11/.
#
# Change Date:    2030-05-01
# Change License: Apache License, Version 2.0
#
# Additional Use Grant: see LICENSE-BSL. Production use is
# permitted; offering a competing hosted service is not.

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
from collections.abc import Sequence
from dataclasses import asdict

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
            f"unknown benchmark {args.benchmark!r}; choose from {sorted(_BENCHMARKS)}",
            file=sys.stderr,
        )
        return 2

    from dendra.benchmarks.rules import build_reference_rule
    from dendra.ml import SklearnTextHead
    from dendra.research import run_benchmark_experiment

    ds = _load_bench(args.benchmark)
    rule = build_reference_rule(
        ds.train,
        seed_size=args.seed_size,
        keywords_per_label=args.kw_per_label,
    ).as_callable()
    head = SklearnTextHead(min_outcomes=args.min_train_for_ml)

    model = _build_lm(args) if args.lm_kind else None
    checkpoints = run_benchmark_experiment(
        train=ds.train,
        test=ds.test,
        rule=rule,
        ml_head=head,
        checkpoint_every=args.checkpoint_every,
        min_train_for_ml=args.min_train_for_ml,
        max_train=args.max_train,
        model=model,
        lm_labels=ds.labels,
        lm_test_sample_size=args.lm_test_sample,
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


def _build_lm(args: argparse.Namespace):
    """Factory — map CLI args to an ModelClassifier instance."""
    from dendra.models import (
        AnthropicAdapter,
        LlamafileAdapter,
        OllamaAdapter,
        OpenAIAdapter,
    )

    kind = args.lm_kind
    if kind == "ollama":
        return OllamaAdapter(model=args.lm_id or "qwen2.5:7b")
    if kind == "llamafile":
        return LlamafileAdapter(model=args.lm_id or "LLaMA_CPP")
    if kind == "openai":
        return OpenAIAdapter(model=args.lm_id or "gpt-4o-mini")
    if kind == "anthropic":
        return AnthropicAdapter(model=args.lm_id or "claude-haiku-4-5")
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


_QUICKSTART_EXAMPLES = {
    "hello": ("01_hello_world.py", "smallest example — rule + dispatch"),
    "tournament": ("21_tournament.py", "pick among N candidates with statistical confidence"),
    "autoresearch": ("19_autoresearch_loop.py", "Karpathy-style propose / evaluate / reflect loop"),
    "verifier": ("20_verifier_default.py", "autonomous-verification default"),
    "exception": ("17_exception_handling.py", "Dendra as a try/except-tree replacement"),
}


def cmd_quickstart(args: argparse.Namespace) -> int:
    """Copy an example into the cwd (or path) and run it.

    The fastest path from `pip install dendra` to "I see it work."
    No git clone, no `cd examples/` — `dendra quickstart` and you're
    looking at output.
    """
    import shutil
    import subprocess
    from importlib import resources
    from pathlib import Path

    if args.list:
        print("Available quickstart examples:")
        for key, (filename, desc) in _QUICKSTART_EXAMPLES.items():
            print(f"  {key:14s} — {desc}")
            print(f"  {'':14s}    ({filename})")
        return 0

    if args.example not in _QUICKSTART_EXAMPLES:
        print(
            f"unknown example {args.example!r}; "
            f"choose from {sorted(_QUICKSTART_EXAMPLES)}",
            file=sys.stderr,
        )
        return 2

    filename, desc = _QUICKSTART_EXAMPLES[args.example]

    # Locate the example. Two cases:
    #  1. Editable install / source checkout — examples/ sits next to src/
    #  2. Wheel install — examples aren't packaged; fetch from GitHub raw.
    #
    # We try the local path first; if it isn't there, fall back to a
    # tagged release on GitHub. Failure is honest — the user gets a
    # clear "neither path worked" message with both URLs.
    here = Path(__file__).resolve()
    repo_root = here.parent.parent.parent
    local_example = repo_root / "examples" / filename

    target_dir = Path(args.target).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    target_file = target_dir / filename

    if local_example.exists():
        shutil.copy2(local_example, target_file)
        # Demo stubs file ships alongside several examples.
        local_stubs = repo_root / "examples" / "_stubs.py"
        if local_stubs.exists():
            shutil.copy2(local_stubs, target_dir / "_stubs.py")
        source = f"local source ({local_example})"
    else:
        import urllib.error
        import urllib.request
        # Wheel install — fetch from the public repo.
        url_base = (
            "https://raw.githubusercontent.com/axiom-labs-os/dendra/main/examples"
        )
        url = f"{url_base}/{filename}"
        try:
            urllib.request.urlretrieve(url, target_file)
            try:
                urllib.request.urlretrieve(
                    f"{url_base}/_stubs.py", target_dir / "_stubs.py"
                )
            except urllib.error.URLError:
                # _stubs.py is optional for some examples; skip silently
                pass
            source = url
        except urllib.error.URLError as e:
            print(
                f"Could not fetch example from {url}: {e}\n"
                f"Recovery: clone the repo "
                f"(git clone https://github.com/axiom-labs-os/dendra) "
                f"and run `python examples/{filename}` directly.",
                file=sys.stderr,
            )
            return 1

    print(f"copied {filename} from {source}")
    print(f"  → {target_file}")
    if args.no_run:
        print(f"\nrun with: python {target_file}")
        return 0
    print(f"\nrunning python {target_file} ...\n" + "-" * 60, flush=True)
    rc = subprocess.run([sys.executable, str(target_file)]).returncode
    print("-" * 60, flush=True)
    if rc == 0:
        print(f"done. The script lives at {target_file} — edit + re-run as you experiment.")
    return rc


def cmd_plot(args: argparse.Namespace) -> int:
    from dendra.viz import load_run, plot_transition_curves

    runs = [load_run(p) for p in args.jsonl]
    plot_transition_curves(
        runs,
        output_path=args.output,
        title=args.title,
    )
    print(f"wrote {args.output}", file=sys.stderr)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
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
    p_bench.add_argument(
        "--seed-size",
        type=int,
        default=100,
        help="Training examples used to construct the rule (paper §4.2).",
    )
    p_bench.add_argument("--kw-per-label", type=int, default=5, help="Keywords selected per label.")
    p_bench.add_argument(
        "--checkpoint-every", type=int, default=250, help="Outcomes between checkpoints."
    )
    p_bench.add_argument(
        "--min-train-for-ml",
        type=int,
        default=100,
        help="Smallest training count at which the ML head is fit.",
    )
    p_bench.add_argument(
        "--max-train", type=int, default=None, help="Cap on training examples (smoke-test knob)."
    )
    p_bench.add_argument(
        "--lm",
        choices=["ollama", "llamafile", "openai", "anthropic"],
        default=None,
        help="Enable language model shadow evaluation with the named provider.",
    )
    p_bench.add_argument("--lm-id", default=None, help="Model ID passed to the language-model provider.")
    p_bench.add_argument(
        "--lm-test-sample",
        type=int,
        default=None,
        help="Subsample size for language model test evaluation (default: full test set).",
    )
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
        help="Include per-site annual savings projection (uses dendra.roi default cost model).",
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
            "RULE",
            "MODEL_SHADOW",
            "MODEL_PRIMARY",
            "ML_SHADOW",
            "ML_WITH_FALLBACK",
            "ML_PRIMARY",
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

    p_quick = sub.add_parser(
        "quickstart",
        help="Copy a runnable example into the current directory and run it.",
    )
    p_quick.add_argument(
        "example",
        nargs="?",
        default="tournament",
        help=(
            "Which example to copy. Default: 'tournament' (picks among "
            "N candidates with statistical confidence). "
            "Use --list to see all options."
        ),
    )
    p_quick.add_argument(
        "--target",
        default=".",
        help="Directory to copy the example into. Default: current directory.",
    )
    p_quick.add_argument(
        "--no-run",
        action="store_true",
        help="Copy the file but don't execute it.",
    )
    p_quick.add_argument(
        "--list",
        action="store_true",
        help="List the available examples and exit.",
    )
    p_quick.set_defaults(fn=cmd_quickstart)

    p_roi = sub.add_parser(
        "roi",
        help="Self-measured ROI report from outcome logs under a FileStorage root.",
    )
    p_roi.add_argument("storage", help="FileStorage base path (dir containing per-switch subdirs).")
    p_roi.add_argument("--json", action="store_true", help="Emit JSON instead of a text report.")
    p_roi.add_argument(
        "--engineer-cost-per-week",
        type=float,
        default=None,
        help="Override fully-loaded eng cost in USD/week.",
    )
    p_roi.add_argument(
        "--monthly-value-low",
        type=float,
        default=None,
        help="Override monthly value per site (low bound).",
    )
    p_roi.add_argument(
        "--monthly-value-high",
        type=float,
        default=None,
        help="Override monthly value per site (high bound).",
    )
    p_roi.set_defaults(fn=cmd_roi)

    p_plot = sub.add_parser(
        "plot",
        help="Plot transition curves from one or more `dendra bench` JSONL files.",
    )
    p_plot.add_argument(
        "jsonl", nargs="+", help="One or more JSONL files produced by `dendra bench`."
    )
    p_plot.add_argument(
        "-o", "--output", required=True, help="Output image path (.png / .svg / .pdf)."
    )
    p_plot.add_argument("--title", default="Dendra transition curves", help="Figure title.")
    p_plot.set_defaults(fn=cmd_plot)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
