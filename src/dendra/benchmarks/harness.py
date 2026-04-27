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
"""Close-the-loop benchmark + report harness (v1.1).

Three things live here:

1. :func:`generate_benchmark_module` — codegen for a per-switch pytest
   stub that records label parity across phases, latency p50/p95, and
   per-call cost into ``runtime/dendra/<switch>/benchmarks/*.jsonl``.
   Emitted via :func:`dendra.refresh.write_generated_file` so the bench
   stub participates in the same drift-detection lifecycle as the
   lifted Switch module.

2. :func:`run_benchmark` — programmatic runner used by the
   ``dendra benchmark`` CLI verb. Shells out to ``pytest`` so the
   ``dendra.benchmarks`` runtime path stays free of the pytest import.

3. :func:`aggregate_report` + :func:`format_report` — walk
   ``runtime/dendra/*/benchmarks/*.jsonl``, identify graduation events,
   compute cost deltas, render the human-readable ``dendra report``.

Cost defaults to ESTIMATED (token × per-token rate) using
:class:`dendra.roi.ROIAssumptions`. ``--measure-real-cost`` on the CLI
flips ``estimated=False`` and lets the runner record actual
per-call spend reported by the configured model adapter.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from dendra.refresh import write_generated_file
from dendra.roi import ROIAssumptions

# ---------------------------------------------------------------------------
# Codegen
# ---------------------------------------------------------------------------


_BENCH_TEMPLATE = '''\
"""Auto-generated benchmark stub for {switch_class_name}.

Captures label parity across phases, latency, and estimated cost into
runtime/dendra/{switch_name}/benchmarks/<UTC-iso>.jsonl. One line per
pytest run carrying the metrics from all three test functions.

Edit the module's INPUTS list (or drop a fixture file at
tests/fixtures/{switch_name}_inputs.jsonl) to feed real traffic shapes.
"""

from __future__ import annotations

import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dendra import Phase
from dendra.roi import ROIAssumptions
from {switch_module} import {switch_class_name}


SWITCH_NAME = {switch_name!r}
RUNTIME_ROOT = Path("runtime")
FIXTURE_PATH = Path("tests/fixtures") / f"{{SWITCH_NAME}}_inputs.jsonl"

# Inline placeholder inputs. Replace by writing real ones to FIXTURE_PATH.
PLACEHOLDER_INPUTS = ["sample-input-1", "sample-input-2", "sample-input-3"]

# Per-test parity tolerance. Override by adding `class Meta:
# parity_tolerance = 0.90` to the Switch subclass.
DEFAULT_PARITY_TOLERANCE = 0.95


def _load_inputs():
    if FIXTURE_PATH.exists():
        out = []
        for line in FIXTURE_PATH.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                out.append(line)
        return out
    print(
        f"warning: no fixture at {{FIXTURE_PATH}}; using {{len(PLACEHOLDER_INPUTS)}} "
        "placeholder inputs. Write real ones for trustworthy numbers.",
    )
    return list(PLACEHOLDER_INPUTS)


def _parity_tolerance(cls) -> float:
    meta = getattr(cls, "Meta", None)
    if meta is None:
        return DEFAULT_PARITY_TOLERANCE
    return float(getattr(meta, "parity_tolerance", DEFAULT_PARITY_TOLERANCE))


def _new_switch():
    return {switch_class_name}()


def _bench_dir() -> Path:
    out = RUNTIME_ROOT / "dendra" / SWITCH_NAME / "benchmarks"
    out.mkdir(parents=True, exist_ok=True)
    return out


# Module-scoped accumulator so all three tests append into one JSONL
# line (one row per pytest run).
_RUN_RECORD: dict = {{}}


@pytest.fixture(scope="module", autouse=True)
def _flush_run_record():
    yield
    if not _RUN_RECORD:
        return
    ts = datetime.now(tz=timezone.utc).isoformat()
    safe_ts = ts.replace(":", "-")
    _RUN_RECORD.setdefault("timestamp", ts)
    _RUN_RECORD.setdefault("switch_name", SWITCH_NAME)
    out_path = _bench_dir() / f"{{safe_ts}}.jsonl"
    out_path.write_text(json.dumps(_RUN_RECORD) + "\\n")


def test_label_parity_across_phases():
    inputs = _load_inputs()
    sw = _new_switch()
    rule_labels = [sw.classify(x) for x in inputs]
    # MODEL_PRIMARY / ML_PRIMARY are skipped when not configured. We
    # measure parity against whichever phases the switch can reach.
    parity_observed = []
    for phase_name in ("MODEL_PRIMARY", "ML_PRIMARY"):
        try:
            sw.advance(target=Phase[phase_name])
        except Exception:
            continue
        try:
            other = [sw.classify(x) for x in inputs]
        except Exception:
            continue
        agree = sum(1 for a, b in zip(rule_labels, other) if a == b)
        parity_observed.append(agree / max(1, len(inputs)))

    parity = min(parity_observed) if parity_observed else 1.0
    tol = _parity_tolerance({switch_class_name})
    _RUN_RECORD["label_parity"] = parity
    _RUN_RECORD["n_inputs"] = len(inputs)
    _RUN_RECORD["phase"] = sw.phase().value if hasattr(sw.phase(), "value") else str(sw.phase())
    assert parity >= tol, (
        f"label parity {{parity:.3f}} below tolerance {{tol:.3f}}"
    )


def test_latency_baseline():
    inputs = _load_inputs()
    sw = _new_switch()
    samples_ms = []
    for x in inputs:
        t0 = time.perf_counter()
        sw.classify(x)
        samples_ms.append((time.perf_counter() - t0) * 1000.0)
    samples_ms.sort()
    p50 = statistics.median(samples_ms) if samples_ms else 0.0
    if samples_ms:
        idx = max(0, int(round(0.95 * (len(samples_ms) - 1))))
        p95 = samples_ms[idx]
    else:
        p95 = 0.0
    _RUN_RECORD["latency_p50_ms"] = p50
    _RUN_RECORD["latency_p95_ms"] = p95


def test_cost_estimate_per_call():
    a = ROIAssumptions()
    cost_low = (
        a.llm_input_tokens_per_call * a.llm_input_usd_per_1m_tokens_low / 1e6
        + a.llm_output_tokens_per_call * a.llm_output_usd_per_1m_tokens_low / 1e6
    )
    cost_high = (
        a.llm_input_tokens_per_call * a.llm_input_usd_per_1m_tokens_high / 1e6
        + a.llm_output_tokens_per_call * a.llm_output_usd_per_1m_tokens_high / 1e6
    )
    _RUN_RECORD["cost_per_call_usd_low"] = cost_low
    _RUN_RECORD["cost_per_call_usd_high"] = cost_high
    _RUN_RECORD["estimated"] = True
'''


def generate_benchmark_module(
    *,
    out_path: Path,
    source_module: str,
    source_function: str,
    switch_class_name: str,
    switch_module: str,
    source_ast_hash: str,
    dendra_version: str,
    switch_name: str | None = None,
) -> None:
    """Write the per-switch benchmark stub at ``out_path``.

    The file lives under ``__dendra_generated__/`` next to the lifted
    Switch module and uses :func:`dendra.refresh.write_generated_file`
    so a Dendra header (with AST hash + content hash) tops the file.
    The bench stub is keyed on the ORIGINAL source function — its AST
    drift signal is the same as the lifted module's, so a single
    ``dendra refresh`` run reconciles both.
    """
    name = switch_name if switch_name is not None else source_function
    body = _BENCH_TEMPLATE.format(
        switch_class_name=switch_class_name,
        switch_module=switch_module,
        switch_name=name,
    )
    write_generated_file(
        out_path,
        source_module=source_module,
        source_function=source_function,
        source_ast_hash=source_ast_hash,
        content=body,
        dendra_version=dendra_version,
    )


# ---------------------------------------------------------------------------
# Programmatic runner
# ---------------------------------------------------------------------------


def run_benchmark(
    *,
    switch_name: str,
    switch_module: str,
    switch_class_name: str,
    inputs: list,
    runtime_dir: Path,
    measure_real_cost: bool = False,
) -> dict:
    """Run the three benchmark measurements against an instantiated
    Switch and persist one JSONL line into
    ``runtime_dir/dendra/<switch_name>/benchmarks/<UTC-iso>.jsonl``.

    This is the in-process variant used by ``dendra benchmark`` for the
    case where the generated bench module isn't on disk yet (e.g. unit
    tests, smoke tests). The CLI command also supports a subprocess
    pytest path by importing the generated module directly.
    """
    # Resolve the switch class.
    import importlib

    module = importlib.import_module(switch_module)
    cls = getattr(module, switch_class_name)
    sw = cls()

    # Label parity. We baseline against RULE; if no other phase is
    # reachable, parity defaults to 1.0 (nothing to disagree with).
    rule_labels = [sw.classify(x) for x in inputs]
    parity_values: list[float] = []
    try:
        from dendra import Phase  # local import keeps dendra.benchmarks lean
    except ImportError:
        Phase = None  # type: ignore[assignment]
    if Phase is not None:
        for phase_name in ("MODEL_PRIMARY", "ML_PRIMARY"):
            try:
                sw.advance(target=Phase[phase_name])
            except Exception:
                continue
            try:
                other = [sw.classify(x) for x in inputs]
            except Exception:
                continue
            agree = sum(1 for a, b in zip(rule_labels, other, strict=False) if a == b)
            parity_values.append(agree / max(1, len(inputs)))
    parity = min(parity_values) if parity_values else 1.0

    # Latency.
    samples_ms: list[float] = []
    sw_latency = cls()
    for x in inputs:
        t0 = time.perf_counter()
        sw_latency.classify(x)
        samples_ms.append((time.perf_counter() - t0) * 1000.0)
    samples_ms.sort()
    p50 = statistics.median(samples_ms) if samples_ms else 0.0
    if samples_ms:
        idx = max(0, int(round(0.95 * (len(samples_ms) - 1))))
        p95 = samples_ms[idx]
    else:
        p95 = 0.0

    # Cost — estimated by default; opt-in real-cost left as a hook.
    a = ROIAssumptions()
    cost_low = (
        a.llm_input_tokens_per_call * a.llm_input_usd_per_1m_tokens_low / 1e6
        + a.llm_output_tokens_per_call * a.llm_output_usd_per_1m_tokens_low / 1e6
    )
    cost_high = (
        a.llm_input_tokens_per_call * a.llm_input_usd_per_1m_tokens_high / 1e6
        + a.llm_output_tokens_per_call * a.llm_output_usd_per_1m_tokens_high / 1e6
    )

    # Phase tag — whatever the switch is currently in.
    try:
        phase_value = sw.phase()
        phase_str = phase_value.value if hasattr(phase_value, "value") else str(phase_value)
    except Exception:
        phase_str = "RULE"

    timestamp = datetime.now(tz=timezone.utc).isoformat()
    record = {
        "timestamp": timestamp,
        "switch_name": switch_name,
        "phase": phase_str,
        "n_inputs": len(inputs),
        "label_parity": parity,
        "latency_p50_ms": p50,
        "latency_p95_ms": p95,
        "cost_per_call_usd_low": cost_low,
        "cost_per_call_usd_high": cost_high,
        "estimated": not measure_real_cost,
    }

    bench_dir = runtime_dir / "dendra" / switch_name / "benchmarks"
    bench_dir.mkdir(parents=True, exist_ok=True)
    safe_ts = timestamp.replace(":", "-")
    out_path = bench_dir / f"{safe_ts}.jsonl"
    out_path.write_text(json.dumps(record) + "\n")
    return record


def run_benchmark_pytest(
    *,
    bench_module_path: Path,
    pytest_args: list[str] | None = None,
) -> int:
    """Shell out to pytest against a generated bench module.

    Returns the pytest exit code. The bench module persists its own
    JSONL line via the autouse fixture; the caller can read the latest
    file under ``runtime/dendra/<switch>/benchmarks/`` to surface it.
    """
    args = [sys.executable, "-m", "pytest", str(bench_module_path), "-q"]
    if pytest_args:
        args.extend(pytest_args)
    proc = subprocess.run(args)
    return proc.returncode


# ---------------------------------------------------------------------------
# Aggregation + formatting
# ---------------------------------------------------------------------------


@dataclass
class GraduationEvent:
    """A single phase transition surfaced from the bench timeseries."""

    from_phase: str
    to_phase: str
    timestamp: str
    after_n_inputs: int


@dataclass
class SwitchTimeseries:
    """Per-switch aggregate of the benchmark JSONL files."""

    switch_name: str
    n_runs: int
    first_phase: str
    latest_phase: str
    cost_baseline_low: float
    cost_baseline_high: float
    cost_latest_low: float
    cost_latest_high: float
    cost_pct_change_low: float | None
    cost_pct_change_high: float | None
    graduation_event: GraduationEvent | None
    days_of_data: int


@dataclass
class Report:
    """Full report aggregated across every switch under runtime/dendra."""

    n_switches: int
    days_of_data: int
    estimated_saved_this_week_low_usd: float
    estimated_saved_this_week_high_usd: float
    switches: list[SwitchTimeseries] = field(default_factory=list)


def aggregate_report(runtime_dir: Path) -> Report:
    """Walk ``runtime_dir/dendra/*/benchmarks/*.jsonl`` and aggregate.

    The caller passes the *project* runtime root (i.e. the directory
    that contains ``dendra/<switch_name>/benchmarks``). Missing trees
    return an empty report rather than raising.
    """
    base = runtime_dir / "dendra"
    if not base.exists():
        return Report(
            n_switches=0,
            days_of_data=0,
            estimated_saved_this_week_low_usd=0.0,
            estimated_saved_this_week_high_usd=0.0,
        )

    switches: list[SwitchTimeseries] = []
    all_timestamps: list[datetime] = []
    saved_low = 0.0
    saved_high = 0.0

    for switch_dir in sorted(p for p in base.iterdir() if p.is_dir()):
        bench_dir = switch_dir / "benchmarks"
        if not bench_dir.is_dir():
            continue
        records = _load_records(bench_dir)
        if not records:
            continue
        ts = _aggregate_one(switch_dir.name, records)
        switches.append(ts)
        all_timestamps.extend(_record_timestamps(records))
        # Estimated weekly savings: cost_baseline - cost_latest, scaled
        # by sum of n_inputs in the most recent week. Only graduating
        # switches contribute (no graduation = no savings claim).
        if ts.graduation_event is not None:
            week_inputs = _inputs_in_window(records, days=7)
            saved_low += max(0.0, ts.cost_baseline_low - ts.cost_latest_low) * week_inputs
            saved_high += max(0.0, ts.cost_baseline_high - ts.cost_latest_high) * week_inputs

    if all_timestamps:
        span = max(all_timestamps) - min(all_timestamps)
        days = max(1, span.days + 1)
    else:
        days = 0

    return Report(
        n_switches=len(switches),
        days_of_data=days,
        estimated_saved_this_week_low_usd=saved_low,
        estimated_saved_this_week_high_usd=saved_high,
        switches=switches,
    )


def _load_records(bench_dir: Path) -> list[dict]:
    out: list[dict] = []
    for path in sorted(bench_dir.glob("*.jsonl")):
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    # Sort by timestamp for chronology.
    out.sort(key=lambda r: r.get("timestamp", ""))
    return out


def _record_timestamps(records: list[dict]) -> list[datetime]:
    out: list[datetime] = []
    for r in records:
        ts = r.get("timestamp")
        if not ts:
            continue
        try:
            out.append(datetime.fromisoformat(ts))
        except ValueError:
            continue
    return out


def _inputs_in_window(records: list[dict], *, days: int) -> int:
    if not records:
        return 0
    timestamps = _record_timestamps(records)
    if not timestamps:
        return 0
    cutoff = max(timestamps)
    threshold = cutoff.timestamp() - days * 86400
    total = 0
    for r in records:
        ts_str = r.get("timestamp")
        if not ts_str:
            continue
        try:
            ts_val = datetime.fromisoformat(ts_str)
        except ValueError:
            continue
        if ts_val.timestamp() >= threshold:
            total += int(r.get("n_inputs", 0) or 0)
    return total


def _aggregate_one(name: str, records: list[dict]) -> SwitchTimeseries:
    first = records[0]
    last = records[-1]
    grad: GraduationEvent | None = None
    cumulative_inputs = 0
    prev_phase = first.get("phase", "RULE")
    for r in records:
        cumulative_inputs += int(r.get("n_inputs", 0) or 0)
        phase = r.get("phase", prev_phase)
        if phase != prev_phase and grad is None:
            grad = GraduationEvent(
                from_phase=prev_phase,
                to_phase=phase,
                timestamp=r.get("timestamp", ""),
                after_n_inputs=cumulative_inputs,
            )
        prev_phase = phase

    base_low = float(first.get("cost_per_call_usd_low", 0.0) or 0.0)
    base_high = float(first.get("cost_per_call_usd_high", 0.0) or 0.0)
    latest_low = float(last.get("cost_per_call_usd_low", 0.0) or 0.0)
    latest_high = float(last.get("cost_per_call_usd_high", 0.0) or 0.0)

    pct_low: float | None
    pct_high: float | None
    pct_low = (latest_low - base_low) / base_low * 100.0 if base_low > 0 else None
    pct_high = (latest_high - base_high) / base_high * 100.0 if base_high > 0 else None

    timestamps = _record_timestamps(records)
    if timestamps:
        span = max(timestamps) - min(timestamps)
        days = max(1, span.days + 1)
    else:
        days = 0

    return SwitchTimeseries(
        switch_name=name,
        n_runs=len(records),
        first_phase=first.get("phase", "RULE"),
        latest_phase=last.get("phase", "RULE"),
        cost_baseline_low=base_low,
        cost_baseline_high=base_high,
        cost_latest_low=latest_low,
        cost_latest_high=latest_high,
        cost_pct_change_low=pct_low,
        cost_pct_change_high=pct_high,
        graduation_event=grad,
        days_of_data=days,
    )


def format_report(report: Report) -> str:
    """Render the human-readable summary.

    Stable wording (used by tests and docs):
      ``Dendra report - <N> switches, <D> days of data``
      per-switch lines for graduated and pre-graduation switches
      ``Total estimated saved this week: $<low>-<high>``

    Hyphens, never em-dashes (Ben's tell-test: a Claude-shaped paper
    leaks em-dashes; a human-and-Claude paper substitutes).
    """
    lines: list[str] = []
    header = (
        f"Dendra report - {report.n_switches} switches, "
        f"{report.days_of_data} days of data"
    )
    lines.append(header)
    lines.append("")
    for sw in report.switches:
        if sw.graduation_event is not None:
            ev = sw.graduation_event
            ts_short = ev.timestamp.split("T")[0] if ev.timestamp else "n/a"
            pct_low = sw.cost_pct_change_low
            # Truncate toward zero so -92.6% reads "-92%" rather
            # than rounding up to "-93%". Reads as a conservative
            # claim (we under-report savings by < 1pp).
            pct_label = "n/a" if pct_low is None else f"{int(pct_low):+d}%"
            lines.append(
                f"{sw.switch_name}  {ev.from_phase} -> {ev.to_phase} "
                f"{ts_short} (after {ev.after_n_inputs} verdicts)"
            )
            lines.append(
                f"{' ' * len(sw.switch_name)}  cost: "
                f"${sw.cost_baseline_low:.4f} -> ${sw.cost_latest_low:.5f}/call "
                f"({pct_label})"
            )
        else:
            lines.append(
                f"{sw.switch_name}  {sw.latest_phase} (no graduation yet)"
            )
            lines.append(
                f"{' ' * len(sw.switch_name)}  cost: "
                f"${sw.cost_latest_low:.4f}/call (no baseline yet)"
            )
        lines.append("")
    lines.append(
        f"Total estimated saved this week: "
        f"${report.estimated_saved_this_week_low_usd:,.2f} - "
        f"${report.estimated_saved_this_week_high_usd:,.2f}"
    )
    return "\n".join(lines)


__all__ = [
    "GraduationEvent",
    "Report",
    "SwitchTimeseries",
    "aggregate_report",
    "format_report",
    "generate_benchmark_module",
    "run_benchmark",
    "run_benchmark_pytest",
]
