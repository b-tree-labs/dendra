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

"""``dendra`` CLI - minimum-viable entry point.

Subcommands:

- ``dendra bench <benchmark>`` - run the transition-curve experiment
  for a named public intent-classification dataset and print JSON-lines
  checkpoints to stdout.

Intentionally argparse-based; no third-party CLI deps.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
import time
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from dendra import auth

# ---------------------------------------------------------------------------
# Account / login flow
#
# v1 scaffolding for relationship-building, not hard DRM. OSS classification
# works without an account; the bare ``dendra`` command is a soft entry
# point that points new users at ``dendra login`` if they want cloud features.
# ---------------------------------------------------------------------------

_DASHBOARD_BASE = "https://app.dendra.ai"
_CLI_AUTH_PATH = "/cli-auth"
_NUDGE_THRESHOLD = 3


def _state_file() -> Path:
    """Resolve the CLI state file lazily.

    Resolved on each call so that the test harness's HOME redirect
    (and any user-set ``HOME`` between invocations) takes effect
    instead of being captured at import time.
    """
    return Path.home() / ".dendra" / "state.toml"


def _strip_unsafe_chars(value: str) -> str:
    """Remove non-printable + ESC bytes from a string before printing it.

    Defense-in-depth: an attacker who manages to land an API key with
    embedded ANSI CSI sequences in the local credentials file (or
    DENDRA_API_KEY env var) would otherwise see those bytes flow into
    a terminal verbatim through ``print()``, and the terminal would
    interpret them as color / cursor-control directives. We never
    pass keys through a shell, but the rendered bytes can still
    confuse log scrapers and any downstream pipe.

    Strategy: keep printable ASCII (``str.isprintable()``) and strip
    everything else (ESC=0x1b, BEL=0x07, BS=0x08, VT=0x0b, FF=0x0c,
    DEL=0x7f, all C0 controls). The underlying credential is
    unchanged; only the rendered form is sanitized.
    """
    return "".join(c for c in value if c.isprintable())


def _truncate_key(api_key: str) -> str:
    """Return a display-safe truncation of an API key.

    The truncation runs through :func:`_strip_unsafe_chars` so a key
    containing ANSI ESC sequences or other control bytes never leaks
    those bytes into stdout when ``dendra login`` / ``dendra whoami``
    print the abbreviation.
    """
    sanitized = _strip_unsafe_chars(api_key)
    if len(sanitized) <= 12:
        return sanitized
    return f"{sanitized[:8]}...{sanitized[-4:]}"


def _load_state() -> dict:
    """Read ~/.dendra/state.toml as a flat key/value dict.

    We hand-parse the small subset we write (int counts, bool flags) to
    avoid a tomllib dependency on Python 3.10. Unknown lines are ignored.
    """
    state_file = _state_file()
    if not state_file.exists():
        return {}
    state: dict = {}
    try:
        for raw in state_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if value.lower() in ("true", "false"):
                state[key] = value.lower() == "true"
            else:
                try:
                    state[key] = int(value)
                except ValueError:
                    state[key] = value.strip('"')
    except OSError:
        return {}
    return state


def _save_state(state: dict) -> None:
    state_file = _state_file()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for key, value in sorted(state.items()):
        if isinstance(value, bool):
            lines.append(f"{key} = {'true' if value else 'false'}")
        elif isinstance(value, int):
            lines.append(f"{key} = {value}")
        else:
            lines.append(f'{key} = "{value}"')
    state_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _maybe_nudge_signup() -> None:
    """One-time soft nudge after repeated unauthenticated use."""
    if auth.is_logged_in():
        return
    state = _load_state()
    if state.get("nudge_shown"):
        return
    count = int(state.get("analyze_count", 0))
    if count < _NUDGE_THRESHOLD:
        return
    print(
        "\nLoving Dendra? Sign up for a free account to enable shared team analysis: dendra login",
        file=sys.stderr,
    )
    state["nudge_shown"] = True
    _save_state(state)


def _bump_counter(key: str) -> None:
    state = _load_state()
    state[key] = int(state.get(key, 0)) + 1
    _save_state(state)


def _switch_class_name_for(func_name: str) -> str:
    """Mirror ``dendra.lifters.evidence._class_name_for`` so the CLI can
    point the benchmark stub at the same class the evidence lifter
    emits (``CamelCaseFuncName + "Switch"``).
    """
    parts = func_name.split("_")
    camel = "".join(p[:1].upper() + p[1:] for p in parts if p)
    return f"{camel}Switch"


def _try_emit_benchmarks(
    *,
    source_path: Path,
    function_name: str,
    original_source: str,
) -> None:
    """Emit the close-the-loop benchmark stub alongside the lifted Switch
    module. Called from ``cmd_init`` when ``--with-benchmarks`` is set.

    The benchmark stub has no runtime dependencies of its own beyond
    pytest (which only the generated file imports, never the runtime
    path). Failures here print to stderr and do not abort the wrap.
    """
    try:
        from dendra import __version__ as _dendra_version
        from dendra import refresh as refresh_mod
        from dendra.benchmarks import generate_benchmark_module
    except ImportError as e:
        print(f"--with-benchmarks: harness unavailable ({e})", file=sys.stderr)
        return

    gen_dir = source_path.parent / "__dendra_generated__"
    bench_path = gen_dir / f"{source_path.stem}__{function_name}_bench.py"
    switch_class_name = _switch_class_name_for(function_name)
    # The lifted module (sibling of the bench module) is imported as
    # ``__dendra_generated__.<file_stem>__<func>``. The exact import
    # path depends on the user's Python package layout; this default
    # matches the sibling-file convention the evidence lifter uses.
    switch_module = f"__dendra_generated__.{source_path.stem}__{function_name}"
    try:
        generate_benchmark_module(
            out_path=bench_path,
            source_module=source_path.stem,
            source_function=function_name,
            switch_class_name=switch_class_name,
            switch_module=switch_module,
            source_ast_hash=refresh_mod.ast_hash(original_source),
            dendra_version=_dendra_version,
            switch_name=function_name,
        )
    except Exception as e:  # noqa: BLE001 - defensive against codegen errors
        print(f"--with-benchmarks: failed to write bench stub ({e})", file=sys.stderr)
        return
    init_path = gen_dir / "__init__.py"
    if not init_path.exists():
        init_path.write_text("")
    print(
        f"--with-benchmarks: wrote {bench_path.relative_to(source_path.parent)}",
        file=sys.stderr,
    )


def _try_auto_lift(
    *,
    source_path: Path,
    function_name: str,
    original_source: str,
) -> None:
    """Run the branch + evidence lifters and emit a Switch subclass into
    ``__dendra_generated__/<file_stem>__<func>.py`` next to the source.

    On refusal: print the first hazard's reason + suggested fix to
    stderr; do NOT raise. The basic decorator was already applied by
    ``cmd_init`` so the user has a working classifier even when full
    lifting can't be done automatically.
    """
    try:
        from dendra import __version__ as _dendra_version
        from dendra import refresh as refresh_mod
        from dendra.lifters.branch import LiftRefused as BranchRefused
        from dendra.lifters.branch import lift_branches
        from dendra.lifters.evidence import LiftRefused as EvidenceRefused
        from dendra.lifters.evidence import lift_evidence
    except ImportError as e:
        print(f"--auto-lift: lifter modules unavailable ({e})", file=sys.stderr)
        return

    # Prefer the evidence lifter (richer output) when it accepts; fall
    # back to the branch lifter for branches without hidden state. Both
    # raise LiftRefused with a structured reason.
    lifted_source: str | None = None
    last_error: str | None = None
    for lifter_name, lifter, refused_cls in (
        ("evidence", lift_evidence, EvidenceRefused),
        ("branch", lift_branches, BranchRefused),
    ):
        try:
            lifted_source = lifter(original_source, function_name)
            lifter_used = lifter_name
            break
        except refused_cls as e:
            last_error = f"{lifter_name}: {e.reason} at line {e.line}"
            continue
        except Exception as e:  # noqa: BLE001 - defensive; lifters shouldn't crash
            last_error = f"{lifter_name}: unexpected error: {e}"
            continue

    if lifted_source is None:
        print(
            "--auto-lift: refused. The basic decorator was applied. "
            f"To extract per-branch handlers and hidden-state evidence, "
            f"resolve the issue and re-run with --auto-lift.\n"
            f"  Reason: {last_error}\n"
            "  Run `dendra analyze --suggest-refactors` for the full diagnostic.",
            file=sys.stderr,
        )
        return

    # Write the generated file. Convention: __dendra_generated__/ sits
    # next to the source file. The generated module is named
    # <source_stem>__<function>.py.
    gen_dir = source_path.parent / "__dendra_generated__"
    gen_path = gen_dir / f"{source_path.stem}__{function_name}.py"
    # Source module path: derive from the file's package position. For
    # v1 simplicity, use the file stem; the lifter-doctor pair already
    # tolerates this convention.
    source_module = source_path.stem
    # Hash the SAME thing the reader (`refresh.detect_drift`) hashes:
    # the post-decoration extracted function source. ``original_source``
    # is the pre-decoration full file; using it directly here would
    # guarantee a hash mismatch on first refresh because the reader
    # extracts just the function (with its newly-added decorator) and
    # hashes only that snippet. Re-read the file to capture the wrapper
    # state already written by ``cmd_init``.
    post_decoration_source = source_path.read_text(encoding="utf-8")
    fn_src = refresh_mod._extract_function_source(post_decoration_source, function_name)
    if fn_src is None:
        # Should not happen: cmd_init just wrapped this function. Fall
        # back to the original source so we at least write a header.
        fn_src = original_source
    refresh_mod.write_generated_file(
        gen_path,
        source_module=source_module,
        source_function=function_name,
        source_ast_hash=refresh_mod.ast_hash(fn_src),
        content=lifted_source,
        dendra_version=_dendra_version,
    )
    # Ensure __dendra_generated__/__init__.py exists so the package is
    # importable. (Empty file is enough.)
    init_path = gen_dir / "__init__.py"
    if not init_path.exists():
        init_path.write_text("")
    print(
        f"--auto-lift: wrote {gen_path.relative_to(source_path.parent)} "
        f"using the {lifter_used} lifter.",
        file=sys.stderr,
    )


def cmd_status(args: argparse.Namespace) -> int:
    """Bare ``dendra`` (no subcommand) - soft welcome / status."""
    creds = auth.load_credentials()
    if creds is None:
        print(
            "Dendra is the graduated-autonomy classification primitive. "
            "OSS features work without an account."
        )
        print()
        print("Run `dendra login` to create a free account and unlock cloud features:")
        print("  - cloud-synced switch configurations")
        print("  - shared team analyzer corpus")
        print("  - opt-in registry contribution")
        print()
        print("See `dendra --help` for the full command list.")
        return 0

    email = creds.get("email") or "unknown"
    print(f"Logged in as {email} ({_truncate_key(creds['api_key'])}).")
    print("Run `dendra --help` for available commands.")
    return 0


def cmd_login(args: argparse.Namespace) -> int:
    """Browser-based device flow.

    v1 stub: prints the dashboard URL with a one-time code, polls a
    stub endpoint, and saves the returned credentials. The real
    polling endpoint is a TODO for the dashboard team; the CLI flow
    works end-to-end against the local stub today.
    """
    code = secrets.token_urlsafe(24)
    auth_url = f"{_DASHBOARD_BASE}{_CLI_AUTH_PATH}?code={code}"

    print("To finish signing in, open this URL in your browser:")
    print()
    print(f"  {auth_url}")
    print()
    print("Waiting for confirmation (Ctrl+C to cancel)...", flush=True)

    # TODO(dashboard): replace this stub with real long-poll against
    # ``POST {API_BASE}/cli-auth/poll`` once the dashboard ships.
    api_key, email = _stub_poll_for_token(code)

    auth.save_credentials(api_key, email=email)
    print()
    print(f"Signed in as {email}.")
    print(f"Credentials saved to {auth.credentials_path()} (mode 0600).")
    return 0


def _stub_poll_for_token(code: str) -> tuple[str, str]:
    """v1 stub: sleep briefly, then mint a deterministic token.

    Replaced by a real HTTP poll once the dashboard exists.
    """
    time.sleep(2)
    return f"dndra_{code[:16]}", "user@example.com"


def cmd_logout(args: argparse.Namespace) -> int:
    """Clear local credentials."""
    if not auth.is_logged_in():
        print("Already signed out.")
        return 0
    auth.clear_credentials()
    print("Signed out. Local credentials removed.")
    return 0


def cmd_whoami(args: argparse.Namespace) -> int:
    """Print the logged-in email + truncated API key."""
    creds = auth.load_credentials()
    if creds is None:
        print("not logged in")
        return 1
    email = creds.get("email") or "(email unknown)"
    print(f"{email}  {_truncate_key(creds['api_key'])}")
    return 0


_BENCHMARKS = {
    "banking77": "load_banking77",
    "clinc150": "load_clinc150",
    "hwu64": "load_hwu64",
    "atis": "load_atis",
    "snips": "load_snips",
    "trec6": "load_trec6",
    "ag_news": "load_ag_news",
    "codelangs": "load_codelangs",
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
        shuffle=not args.no_shuffle,
        shuffle_seed=args.shuffle_seed,
    ).as_callable()
    head = SklearnTextHead(min_outcomes=args.min_train_for_ml)

    model = _build_lm(args) if args.lm else None
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
        "shuffle": not args.no_shuffle,
        "shuffle_seed": args.shuffle_seed,
        "checkpoint_every": args.checkpoint_every,
        "citation": ds.citation,
    }
    print(json.dumps({"kind": "summary", **summary}))
    for cp in checkpoints:
        print(json.dumps({"kind": "checkpoint", **asdict(cp)}))

    return 0


def _build_lm(args: argparse.Namespace):
    """Factory - map CLI args to an ModelClassifier instance."""
    from dendra.models import (
        AnthropicAdapter,
        LlamafileAdapter,
        OllamaAdapter,
        OpenAIAdapter,
    )

    kind = args.lm
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
    _bump_counter("analyze_count")
    _maybe_nudge_signup()
    return 0


def cmd_init(args: argparse.Namespace) -> int:
    """Wrap a target function with @ml_switch via AST injection."""
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

    # --auto-lift: run the lifters on the (now-wrapped) source and emit
    # a Switch subclass into __dendra_generated__/. The basic decorator
    # was already applied above so the user gets *something* even if
    # the lifter refuses.
    if getattr(args, "auto_lift", False):
        _try_auto_lift(
            source_path=path,
            function_name=function_name,
            original_source=source,
        )

    if getattr(args, "with_benchmarks", False):
        _try_emit_benchmarks(
            source_path=path,
            function_name=function_name,
            original_source=source,
        )

    _bump_counter("init_count")
    state = _load_state()
    # The first successful `init` is a teachable moment - show the nudge
    # once even if the analyze threshold has not been reached.
    if (
        int(state.get("init_count", 0)) == 1
        and not auth.is_logged_in()
        and not state.get("nudge_shown")
    ):
        print(
            "\nLoving Dendra? Sign up for a free account to enable shared "
            "team analysis: dendra login",
            file=sys.stderr,
        )
        state["nudge_shown"] = True
        _save_state(state)
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
    "hello": ("01_hello_world.py", "smallest example - rule + dispatch"),
    "tournament": ("21_tournament.py", "pick among N candidates with statistical confidence"),
    "autoresearch": ("19_autoresearch_loop.py", "Karpathy-style propose / evaluate / reflect loop"),
    "verifier": ("20_verifier_default.py", "autonomous-verification default"),
    "exception": ("17_exception_handling.py", "Dendra as a try/except-tree replacement"),
}


def cmd_quickstart(args: argparse.Namespace) -> int:
    """Copy an example into the cwd (or path) and run it.

    The fastest path from `pip install dendra` to "I see it work."
    No git clone, no `cd examples/` - `dendra quickstart` and you're
    looking at output.
    """
    import shutil
    import subprocess
    from pathlib import Path

    if args.list:
        print("Available quickstart examples:")
        for key, (filename, desc) in _QUICKSTART_EXAMPLES.items():
            print(f"  {key:14s} - {desc}")
            print(f"  {'':14s}    ({filename})")
        return 0

    if args.example not in _QUICKSTART_EXAMPLES:
        print(
            f"unknown example {args.example!r}; choose from {sorted(_QUICKSTART_EXAMPLES)}",
            file=sys.stderr,
        )
        return 2

    filename, desc = _QUICKSTART_EXAMPLES[args.example]

    # Locate the example. Three cases, tried in order:
    #  1. Editable install / source checkout - examples/ sits next to src/
    #  2. Wheel install - examples bundled under dendra/_examples/
    #  3. Last-ditch fallback - fetch from public repo (only works
    #     post-launch, requires network)
    here = Path(__file__).resolve()
    repo_root = here.parent.parent.parent
    local_example = repo_root / "examples" / filename
    bundled_example = here.parent / "_examples" / filename

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
    elif bundled_example.exists():
        shutil.copy2(bundled_example, target_file)
        bundled_stubs = here.parent / "_examples" / "_stubs.py"
        if bundled_stubs.exists():
            shutil.copy2(bundled_stubs, target_dir / "_stubs.py")
        source = f"bundled with dendra package ({bundled_example})"
    else:
        import urllib.error
        import urllib.request

        # Last-ditch: fetch from public repo (requires repo to be public + network).
        url_base = "https://raw.githubusercontent.com/axiom-labs-os/dendra/main/examples"
        url = f"{url_base}/{filename}"
        try:
            urllib.request.urlretrieve(url, target_file)
            try:
                urllib.request.urlretrieve(f"{url_base}/_stubs.py", target_dir / "_stubs.py")
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
        print(f"done. The script lives at {target_file} - edit + re-run as you experiment.")
    return rc


def cmd_refresh(args: argparse.Namespace) -> int:
    """Walk a project for `__dendra_generated__/` files; check or
    regenerate them against the current source.

    Modes:
      --check : exit non-zero if anything would be regenerated (CI gate).
      (default): regenerate stale files; refuse user-edited ones unless
                 --force is also passed.
    """
    from dendra import refresh as refresh_mod

    root = Path(args.path).resolve() if args.path else Path.cwd()
    if not root.exists():
        sys.stderr.write(f"path does not exist: {root}\n")
        return 2

    # Find all generated files under root: any *.py in a directory named
    # __dendra_generated__.
    #
    # SECURITY: refuse to follow symlinks that escape the project root.
    # ``Path.rglob`` resolves directory entries by default, so a
    # ``__dendra_generated__`` symlink pointing outside ``root`` would
    # otherwise let the walker glob (and parse-read) arbitrary *.py
    # files on the filesystem. No code is executed - parse_generated_header
    # only reads the header - but presenting an out-of-tree path is
    # itself a leak. We require both the symlink itself AND each *.py
    # under it to resolve under ``root`` before honoring them.
    root_resolved = root.resolve()
    generated_files: list[Path] = []
    for gen_dir in root.rglob("__dendra_generated__"):
        if not gen_dir.is_dir():
            continue
        try:
            gen_resolved = gen_dir.resolve()
        except OSError:
            continue
        if not gen_resolved.is_relative_to(root_resolved):
            sys.stderr.write(
                f"refusing to walk {gen_dir}: resolves outside project root "
                f"{root} (symlink escape).\n"
            )
            continue
        for f in gen_dir.glob("*.py"):
            if f.name == "__init__.py":
                continue
            try:
                f_resolved = f.resolve()
            except OSError:
                continue
            if not f_resolved.is_relative_to(root_resolved):
                sys.stderr.write(
                    f"refusing to inspect {f}: resolves outside project root {root}.\n"
                )
                continue
            generated_files.append(f)

    if not generated_files:
        print(f"No Dendra-generated files found under {root}.")
        return 0

    counts = {
        refresh_mod.DriftStatus.UP_TO_DATE: 0,
        refresh_mod.DriftStatus.SOURCE_DRIFT: 0,
        refresh_mod.DriftStatus.USER_EDITED: 0,
        refresh_mod.DriftStatus.MISSING_GENERATED: 0,
        refresh_mod.DriftStatus.ORPHANED: 0,
    }
    drifted: list[tuple[Path, refresh_mod.DriftStatus, str]] = []

    for gen_path in generated_files:
        try:
            header = refresh_mod.parse_generated_header(gen_path.read_text())
        except ValueError as e:
            sys.stderr.write(f"{gen_path}: malformed header ({e})\n")
            continue
        # Resolve source path from module name. Convention: source lives
        # one directory up (sibling of __dendra_generated__/). If the
        # module's last segment matches a .py file in the parent dir,
        # use that. Otherwise skip with a diagnostic.
        parent = gen_path.parent.parent
        last_segment = header.source_module.rsplit(".", 1)[-1]
        candidate = parent / f"{last_segment}.py"
        if not candidate.exists():
            sys.stderr.write(
                f"{gen_path}: cannot locate source file for "
                f"{header.source_module}:{header.source_function}\n"
            )
            continue
        status = refresh_mod.detect_drift(candidate, header.source_function, gen_path)
        counts[status] += 1
        if status is not refresh_mod.DriftStatus.UP_TO_DATE:
            drifted.append((gen_path, status, header.source_function))

    print(
        f"Scanned {len(generated_files)} generated file(s) under {root}:\n"
        f"  up_to_date:        {counts[refresh_mod.DriftStatus.UP_TO_DATE]}\n"
        f"  source_drift:      {counts[refresh_mod.DriftStatus.SOURCE_DRIFT]}\n"
        f"  user_edited:       {counts[refresh_mod.DriftStatus.USER_EDITED]}\n"
        f"  orphaned:          {counts[refresh_mod.DriftStatus.ORPHANED]}\n"
        f"  missing_generated: {counts[refresh_mod.DriftStatus.MISSING_GENERATED]}\n"
    )
    if drifted:
        print("Drift details:")
        for gen_path, status, fn_name in drifted:
            print(f"  [{status.value}] {gen_path.relative_to(root)} (function {fn_name!r})")

    needs_regen = (
        counts[refresh_mod.DriftStatus.SOURCE_DRIFT]
        + counts[refresh_mod.DriftStatus.MISSING_GENERATED]
    )
    needs_attention = (
        needs_regen
        + counts[refresh_mod.DriftStatus.USER_EDITED]
        + counts[refresh_mod.DriftStatus.ORPHANED]
    )

    if args.check:
        return 0 if needs_attention == 0 else 1

    # Default mode: actually regenerate. v1 cuts this scope: print what
    # WOULD be regenerated and direct user to run the lifters explicitly.
    # Auto-regeneration (re-invoking the lifter) lands once the lifter
    # CLI surface is stable.
    if needs_regen:
        print(
            f"\nWould regenerate {needs_regen} file(s). Re-run "
            "`dendra init --auto-lift <file>:<func>` for each, or pass "
            "--check to use this command as a CI gate only."
        )
    if counts[refresh_mod.DriftStatus.USER_EDITED] and not args.force:
        print(
            f"\nRefused to touch {counts[refresh_mod.DriftStatus.USER_EDITED]} "
            "user-edited file(s). Pass --force to overwrite."
        )
        return 1
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Diagnostic walk: report missing, orphaned, and corrupted generated
    files. Read-only; never modifies anything.
    """
    from dendra import refresh as refresh_mod

    root = Path(args.path).resolve() if args.path else Path.cwd()
    if not root.exists():
        sys.stderr.write(f"path does not exist: {root}\n")
        return 2

    print(f"Dendra doctor: scanning {root}\n")
    issues = 0

    for gen_dir in root.rglob("__dendra_generated__"):
        if not gen_dir.is_dir():
            continue
        for gen_path in gen_dir.glob("*.py"):
            if gen_path.name == "__init__.py":
                continue
            try:
                header = refresh_mod.parse_generated_header(gen_path.read_text())
            except ValueError as e:
                print(f"  [malformed] {gen_path.relative_to(root)}: {e}")
                issues += 1
                continue
            parent = gen_path.parent.parent
            last_segment = header.source_module.rsplit(".", 1)[-1]
            candidate = parent / f"{last_segment}.py"
            if not candidate.exists():
                print(
                    f"  [orphan-source] {gen_path.relative_to(root)}: "
                    f"source file for {header.source_module} not found"
                )
                issues += 1
                continue
            status = refresh_mod.detect_drift(candidate, header.source_function, gen_path)
            if status is refresh_mod.DriftStatus.UP_TO_DATE:
                continue
            print(
                f"  [{status.value}] {gen_path.relative_to(root)} "
                f"(function {header.source_function!r})"
            )
            issues += 1

    if issues == 0:
        print("All generated files are healthy.")
        return 0
    print(f"\n{issues} issue(s) found. Run `dendra refresh` to repair stale files.")
    return 1


def cmd_mcp(args: argparse.Namespace) -> int:
    """Run the Dendra MCP server over stdio.

    Exposes Dendra's CLI surface (analyze, init, refresh, doctor) as
    Model Context Protocol tools so Claude Code (and other MCP-aware
    agents) can drive Dendra inside an existing codebase.

    The mcp Python package is an optional dependency; install it with
    ``pip install dendra[mcp]`` if it is missing.
    """
    try:
        from dendra.mcp_server import serve_stdio
    except ImportError as e:
        print(
            f"dendra mcp: {e}\nHint: pip install 'dendra[mcp]'",
            file=sys.stderr,
        )
        return 2
    serve_stdio()
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    """Run the close-the-loop benchmark for one switch.

    Resolves the generated bench module under
    ``__dendra_generated__/<file_stem>__<function>_bench.py`` and
    shells out to pytest. The bench module persists one JSONL row to
    ``runtime/dendra/<switch>/benchmarks/<UTC-iso>.jsonl`` per run.

    On success: prints headline numbers (latest run vs. baseline run,
    or ``first run`` when no prior file exists). Exit code 0 on parity
    within tolerance; non-zero on regression.
    """
    from dendra.benchmarks import aggregate_report, run_benchmark_pytest

    try:
        file_path, function_name = args.target.rsplit(":", 1)
    except ValueError:
        print(
            f"target must be FILE:FUNCTION (got {args.target!r})",
            file=sys.stderr,
        )
        return 2

    src_path = Path(file_path)
    bench_path = (
        src_path.parent / "__dendra_generated__" / f"{src_path.stem}__{function_name}_bench.py"
    )
    if not bench_path.exists():
        print(
            f"dendra benchmark: no bench stub at {bench_path}.\n"
            f"Run `dendra init --auto-lift --with-benchmarks {args.target}` "
            f"to generate it.",
            file=sys.stderr,
        )
        return 2

    rc = run_benchmark_pytest(
        bench_module_path=bench_path,
        pytest_args=(["--tb=short"] if args.measure_real_cost else None),
    )

    # Surface the latest persisted line versus the prior baseline.
    runtime_root = Path(args.runtime) if args.runtime else Path("runtime")
    report = aggregate_report(runtime_root)
    target = next((s for s in report.switches if s.switch_name == function_name), None)
    if target is None:
        print("dendra benchmark: ran, but no JSONL files were persisted.", file=sys.stderr)
        return rc or 1
    if target.n_runs == 1:
        print(
            f"{function_name}: first run "
            f"(phase={target.latest_phase}, "
            f"cost ${target.cost_latest_low:.5f}-${target.cost_latest_high:.5f}/call)"
        )
    else:
        pct = target.cost_pct_change_low
        pct_label = f"{pct:+.1f}%" if pct is not None else "n/a"
        print(
            f"{function_name}: phase {target.first_phase} -> {target.latest_phase}, "
            f"cost ${target.cost_baseline_low:.5f} -> ${target.cost_latest_low:.5f}/call "
            f"({pct_label})"
        )
    return rc


def cmd_report(args: argparse.Namespace) -> int:
    """Walk runtime/dendra/*/benchmarks/*.jsonl and print the report."""
    from dendra.benchmarks import aggregate_report, format_report

    runtime_root = Path(args.runtime) if args.runtime else Path("runtime")
    report = aggregate_report(runtime_root)
    print(format_report(report))
    return 0


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
    from dendra import __version__

    parser = argparse.ArgumentParser(prog="dendra")
    parser.add_argument(
        "--version",
        action="version",
        version=f"dendra {__version__}",
    )
    # Bare `dendra` (no subcommand) routes to cmd_status - the soft entry
    # point for new users. Subcommands are still discoverable via --help.
    parser.set_defaults(fn=cmd_status, cmd=None)
    sub = parser.add_subparsers(dest="cmd", required=False)

    p_bench = sub.add_parser(
        "bench",
        help="Run the transition-curve experiment on a public benchmark.",
    )
    p_bench.add_argument(
        "benchmark",
        choices=sorted(_BENCHMARKS),
        help="Benchmark ID (banking77 | clinc150 | hwu64 | atis | snips).",
    )
    p_bench.add_argument(
        "--seed-size",
        type=int,
        default=100,
        help="Training examples used to construct the rule (paper §4.2).",
    )
    p_bench.add_argument("--kw-per-label", type=int, default=5, help="Keywords selected per label.")
    p_bench.add_argument(
        "--no-shuffle",
        action="store_true",
        help=(
            "Disable the deterministic shuffle of the training stream "
            "before the seed window is taken. The default shuffles with "
            "seed 0 so label-sorted upstream splits (Banking77, HWU64, "
            "CLINC150, Snips on HuggingFace) cannot collapse the rule "
            "to a single label. Pass --no-shuffle to reproduce the v0.x "
            "paper-as-shipped behavior."
        ),
    )
    p_bench.add_argument(
        "--shuffle-seed",
        type=int,
        default=0,
        help=(
            "Seed for the deterministic training-stream shuffle. "
            "Repeated runs with the same seed produce the same rule. "
            "Ignored when --no-shuffle is set."
        ),
    )
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
    p_bench.add_argument(
        "--lm-id", default=None, help="Model ID passed to the language-model provider."
    )
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
        help="FILE:FUNCTION - e.g., src/triage.py:triage_ticket",
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
    p_init.add_argument(
        "--auto-lift",
        action="store_true",
        help=(
            "Also run the branch + evidence lifters and emit a Switch "
            "subclass into __dendra_generated__/ next to the source. "
            "On REFUSAL, prints a specific diagnostic and exits 0 with "
            "the basic decorator still applied."
        ),
    )
    p_init.add_argument(
        "--with-benchmarks",
        action="store_true",
        help=(
            "Also emit a per-switch benchmark stub at "
            "__dendra_generated__/<file>__<func>_bench.py. The stub "
            "persists label-parity, latency, and per-call cost to "
            "runtime/dendra/<switch>/benchmarks/. Use `dendra benchmark` "
            "to run it; `dendra report` to aggregate across switches."
        ),
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

    p_benchmark = sub.add_parser(
        "benchmark",
        help=(
            "Run the close-the-loop benchmark for one switch (label parity "
            "across phases + latency + per-call cost). Persists one JSONL "
            "row to runtime/dendra/<switch>/benchmarks/."
        ),
    )
    p_benchmark.add_argument(
        "target",
        help="FILE:FUNCTION - same shape as `dendra init`.",
    )
    p_benchmark.add_argument(
        "--runtime",
        default=None,
        help="Project runtime root (default: ./runtime).",
    )
    p_benchmark.add_argument(
        "--measure-real-cost",
        action="store_true",
        help=(
            "Calls the configured model adapter and records actual "
            "per-call spend. Off by default to avoid surprise charges."
        ),
    )
    p_benchmark.set_defaults(fn=cmd_benchmark)

    p_report = sub.add_parser(
        "report",
        help=(
            "Aggregate runtime/dendra/*/benchmarks/*.jsonl across all "
            "switches and print a human-readable summary."
        ),
    )
    p_report.add_argument(
        "--runtime",
        default=None,
        help="Project runtime root (default: ./runtime).",
    )
    p_report.set_defaults(fn=cmd_report)

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

    p_login = sub.add_parser(
        "login",
        help="Sign in to Dendra (browser-based, free account).",
    )
    p_login.set_defaults(fn=cmd_login)

    p_logout = sub.add_parser(
        "logout",
        help="Clear local Dendra credentials.",
    )
    p_logout.set_defaults(fn=cmd_logout)

    p_whoami = sub.add_parser(
        "whoami",
        help="Show the signed-in account email and a truncated API key.",
    )
    p_whoami.set_defaults(fn=cmd_whoami)

    p_mcp = sub.add_parser(
        "mcp",
        help=(
            "Run the Dendra MCP server over stdio (for Claude Code et al.). "
            "Requires the mcp extra: pip install 'dendra[mcp]'."
        ),
    )
    p_mcp.set_defaults(fn=cmd_mcp)

    p_refresh = sub.add_parser(
        "refresh",
        help=("Check or regenerate Dendra-generated files in __dendra_generated__/."),
    )
    p_refresh.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Project root to scan (default: current directory).",
    )
    p_refresh.add_argument(
        "--check",
        action="store_true",
        help="Don't regenerate; exit non-zero if any drift found (CI mode).",
    )
    p_refresh.add_argument(
        "--force",
        action="store_true",
        help="Overwrite user-edited generated files (default: refuse).",
    )
    p_refresh.set_defaults(fn=cmd_refresh)

    p_doctor = sub.add_parser(
        "doctor",
        help="Diagnose missing/orphaned/corrupted Dendra-generated files (read-only).",
    )
    p_doctor.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Project root to scan (default: current directory).",
    )
    p_doctor.set_defaults(fn=cmd_doctor)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
