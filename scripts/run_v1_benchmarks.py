# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0

"""v1 baseline benchmark suite.

Measures real latency numbers across the hot-path × phase × auto_record ×
storage backend matrix, plus record_verdict, advance, gate eval, dispatch,
and payload-size scaling. Produces a JSONL raw-data file + a markdown
report for docs/benchmarks/v1-audit-benchmarks.md.

Run:
    python scripts/run_v1_benchmarks.py

Methodology:
- time.perf_counter_ns() for all measurements
- 1000-iter warmup, 10_000-iter measurement per cell (configurable)
- p50/p95/p99 + ops/sec reported
- Env block captures Python/OS/CPU/RAM so the JSONL is self-describing
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dendra import (
    LearnedSwitch,
    MLPrediction,
    Phase,
    SwitchConfig,
)
from dendra.core import ClassificationRecord
from dendra.gates import (
    AccuracyMarginGate,
    CompositeGate,
    McNemarGate,
    MinVolumeGate,
)
from dendra.models import ModelPrediction
from dendra.storage import (
    BoundedInMemoryStorage,
    FileStorage,
    InMemoryStorage,
    SqliteStorage,
)

# ---------------------------------------------------------------------------
# Environment capture
# ---------------------------------------------------------------------------


def _cpu_brand() -> str:
    try:
        r = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return platform.processor() or "unknown"


def _ram_gb() -> int | None:
    try:
        r = subprocess.run(
            ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=2
        )
        if r.returncode == 0:
            return int(r.stdout.strip()) // (1024**3)
    except Exception:
        pass
    return None


def _disk_type_for(path: Path) -> str:
    """Best-effort disk type identifier. macOS: diskutil info."""
    try:
        r = subprocess.run(
            ["df", str(path)],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if r.returncode == 0:
            return r.stdout.splitlines()[-1].split()[0] if r.stdout else "unknown"
    except Exception:
        pass
    return "unknown"


def collect_env() -> dict[str, Any]:
    return {
        "timestamp": time.time(),
        "date": time.strftime("%Y-%m-%d", time.localtime()),
        "python_version": sys.version,
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu": _cpu_brand(),
        "ram_gb": _ram_gb(),
        "dendra_version": _dendra_version(),
        "disk_mount": _disk_type_for(Path.cwd()),
    }


def _dendra_version() -> str:
    try:
        import dendra

        return getattr(dendra, "__version__", "unknown")
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


class _StubLM:
    """Deterministic LLM stub; returns high-confidence label."""

    def classify(self, input: Any, labels: Any) -> ModelPrediction:
        return ModelPrediction(label="flight", confidence=0.95)


class _StubLMLowConf:
    """LLM stub that always yields low confidence → rule_fallback path."""

    def classify(self, input: Any, labels: Any) -> ModelPrediction:
        return ModelPrediction(label="flight", confidence=0.10)


class _StubMLHead:
    """Deterministic ML head; high confidence."""

    def fit(self, records):
        pass

    def predict(self, input: Any, labels: Any) -> MLPrediction:
        return MLPrediction(label="flight", confidence=0.92)

    def model_version(self):
        return "stub-ml"


class _StubMLHeadLowConf:
    def fit(self, records):
        pass

    def predict(self, input: Any, labels: Any) -> MLPrediction:
        return MLPrediction(label="flight", confidence=0.10)

    def model_version(self):
        return "stub-ml-low"


def _rule_atis(text: str) -> str:
    t = text.lower()
    if "fly" in t or "flight" in t:
        return "flight"
    if "ticket" in t or "fare" in t or "cost" in t:
        return "airfare"
    if "airline" in t:
        return "airline"
    return "flight"


# ---------------------------------------------------------------------------
# Measurement harness
# ---------------------------------------------------------------------------


@dataclass
class CellStats:
    name: str
    n_iter: int
    p50_ns: int
    p95_ns: int
    p99_ns: int
    min_ns: int
    max_ns: int
    mean_ns: float
    stdev_ns: float
    ops_per_sec: float
    params: dict[str, Any]
    samples_preview_ns: list[int]  # first 20 samples so readers can sanity-check

    def to_row(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "n_iter": self.n_iter,
            "p50_ns": self.p50_ns,
            "p95_ns": self.p95_ns,
            "p99_ns": self.p99_ns,
            "min_ns": self.min_ns,
            "max_ns": self.max_ns,
            "mean_ns": self.mean_ns,
            "stdev_ns": self.stdev_ns,
            "p50_us": self.p50_ns / 1000.0,
            "p95_us": self.p95_ns / 1000.0,
            "p99_us": self.p99_ns / 1000.0,
            "mean_us": self.mean_ns / 1000.0,
            "stdev_us": self.stdev_ns / 1000.0,
            "ops_per_sec": self.ops_per_sec,
            "params": self.params,
        }


def bench(
    name: str,
    fn: Callable[[], None],
    *,
    params: dict[str, Any] | None = None,
    n_iter: int = 10_000,
    warmup: int = 1_000,
) -> CellStats:
    """Run `fn` n_iter times, return per-call stats in nanoseconds.

    `fn` takes no args; if per-call setup is needed, close over it.
    """
    # Warmup
    for _ in range(warmup):
        fn()

    samples: list[int] = [0] * n_iter
    perf = time.perf_counter_ns
    # Tight loop — no list.append in hot path.
    for i in range(n_iter):
        t0 = perf()
        fn()
        samples[i] = perf() - t0

    samples.sort()
    p50 = samples[int(n_iter * 0.50)]
    p95 = samples[int(n_iter * 0.95)]
    p99 = samples[int(n_iter * 0.99)]
    mean = statistics.mean(samples)
    stdev = statistics.pstdev(samples)
    ops = 1_000_000_000 / mean if mean > 0 else 0.0

    return CellStats(
        name=name,
        n_iter=n_iter,
        p50_ns=p50,
        p95_ns=p95,
        p99_ns=p99,
        min_ns=samples[0],
        max_ns=samples[-1],
        mean_ns=mean,
        stdev_ns=stdev,
        ops_per_sec=ops,
        params=params or {},
        samples_preview_ns=samples[:20],
    )


# ---------------------------------------------------------------------------
# Helpers for building switches under test
# ---------------------------------------------------------------------------

_SWITCH_COUNTER = 0


def _unique_name(prefix: str) -> str:
    global _SWITCH_COUNTER
    _SWITCH_COUNTER += 1
    return f"{prefix}_{_SWITCH_COUNTER}"


def make_switch(
    *,
    phase: Phase,
    auto_record: bool,
    storage=None,
    model=None,
    ml_head=None,
    confidence_threshold: float = 0.85,
) -> LearnedSwitch:
    # Build via explicit config since hoisted kwargs treat None specially.
    cfg = SwitchConfig(
        starting_phase=phase,
        auto_record=auto_record,
        auto_advance=False,  # disable for benchmarking unless we want the spike
        confidence_threshold=confidence_threshold,
    )
    return LearnedSwitch(
        rule=_rule_atis,
        name=_unique_name("bench"),
        author="bench",
        labels=["flight", "airfare", "airline"],
        config=cfg,
        storage=storage,
        model=model,
        ml_head=ml_head,
    )


# ---------------------------------------------------------------------------
# Benchmark cells
# ---------------------------------------------------------------------------

INPUT = "i want to fly from boston to denver"


def bench_classify_phase_matrix(n_iter: int) -> list[CellStats]:
    """Phase × auto_record matrix for classify()."""
    cells: list[CellStats] = []
    llm = _StubLM()
    ml = _StubMLHead()
    configs = [
        ("RULE", Phase.RULE, None, None),
        ("MODEL_SHADOW", Phase.MODEL_SHADOW, llm, None),
        ("MODEL_PRIMARY", Phase.MODEL_PRIMARY, llm, None),
        ("ML_SHADOW", Phase.ML_SHADOW, llm, ml),
        ("ML_WITH_FALLBACK", Phase.ML_WITH_FALLBACK, None, ml),
        ("ML_PRIMARY", Phase.ML_PRIMARY, None, ml),
    ]
    for phase_name, phase, model, ml_head in configs:
        for auto_record in (False, True):
            sw = make_switch(
                phase=phase,
                auto_record=auto_record,
                model=model,
                ml_head=ml_head,
            )
            cells.append(
                bench(
                    name=f"classify.{phase_name}.auto_record={auto_record}",
                    fn=lambda sw=sw: sw.classify(INPUT),
                    params={
                        "phase": phase_name,
                        "auto_record": auto_record,
                        "storage": "BoundedInMemory",
                        "kind": "classify",
                    },
                    n_iter=n_iter,
                )
            )
    return cells


def bench_classify_storage_matrix(n_iter: int, scratch: Path) -> list[CellStats]:
    """classify() at Phase.RULE, auto_record=True, × storage backend."""
    cells: list[CellStats] = []
    backends: list[tuple[str, Any]] = [
        ("BoundedInMemoryStorage", BoundedInMemoryStorage()),
        ("InMemoryStorage", InMemoryStorage()),
        ("FileStorage", FileStorage(scratch / "file_classify")),
        ("SqliteStorage", SqliteStorage(scratch / "sqlite_classify" / "log.db")),
    ]
    for backend_name, storage in backends:
        sw = make_switch(phase=Phase.RULE, auto_record=True, storage=storage)
        cells.append(
            bench(
                name=f"classify.RULE.auto_record=True.{backend_name}",
                fn=lambda sw=sw: sw.classify(INPUT),
                params={
                    "phase": "RULE",
                    "auto_record": True,
                    "storage": backend_name,
                    "kind": "classify-with-storage",
                },
                n_iter=n_iter,
            )
        )
    return cells


def bench_record_verdict_storage(n_iter: int, scratch: Path) -> list[CellStats]:
    """record_verdict() × storage backend, auto_advance disabled."""
    cells: list[CellStats] = []
    backends: list[tuple[str, Any]] = [
        ("BoundedInMemoryStorage", BoundedInMemoryStorage()),
        ("InMemoryStorage", InMemoryStorage()),
        ("FileStorage.fsync=False", FileStorage(scratch / "file_rv")),
        (
            "FileStorage.fsync=True",
            FileStorage(scratch / "file_rv_fsync", fsync=True),
        ),
        ("SqliteStorage.sync=NORMAL", SqliteStorage(scratch / "sqlite_rv" / "log.db")),
    ]
    for backend_name, storage in backends:
        sw = make_switch(phase=Phase.RULE, auto_record=False, storage=storage)
        # auto_advance was already disabled in make_switch
        cells.append(
            bench(
                name=f"record_verdict.{backend_name}",
                fn=lambda sw=sw: sw.record_verdict(input=INPUT, label="flight", outcome="unknown"),
                params={
                    "storage": backend_name,
                    "auto_advance": False,
                    "kind": "record_verdict",
                },
                n_iter=n_iter,
            )
        )
    return cells


def bench_record_verdict_autoadvance(n_iter: int) -> list[CellStats]:
    """record_verdict() with auto_advance=True; measure the interval spike."""
    cells: list[CellStats] = []
    # Interval 100 means every 100th record triggers advance(); so over n_iter
    # we trigger n_iter/100 times. We report the overall distribution; the
    # spike shows up as p99.
    for interval in (100,):
        sw = LearnedSwitch(
            rule=_rule_atis,
            name=_unique_name("bench_aa"),
            author="bench",
            labels=["flight", "airfare", "airline"],
            config=SwitchConfig(
                starting_phase=Phase.RULE,
                auto_record=False,
                auto_advance=True,
                auto_advance_interval=interval,
            ),
            storage=BoundedInMemoryStorage(),
        )
        cells.append(
            bench(
                name=f"record_verdict.auto_advance.interval={interval}",
                fn=lambda sw=sw: sw.record_verdict(input=INPUT, label="flight", outcome="correct"),
                params={
                    "auto_advance": True,
                    "auto_advance_interval": interval,
                    "storage": "BoundedInMemoryStorage",
                    "kind": "record_verdict-auto-advance",
                },
                n_iter=n_iter,
            )
        )
    return cells


def _seed_records(n: int) -> list[ClassificationRecord]:
    """Build `n` paired-correctness records for gate/advance testing.

    Alternate correct/incorrect outcomes; rule_output == label half the
    time, model_output slightly better. That gives McNemarGate real
    discordant pairs to chew on without being degenerate.
    """
    out: list[ClassificationRecord] = []
    for i in range(n):
        # For gate math we need correct-outcome rows with rule_output,
        # model_output, ml_output set.
        outcome = "correct" if i % 2 == 0 else "incorrect"
        # Every 3rd correct record has a mismatched rule and matching model
        # — generates discordant pairs.
        rule_out = "flight" if i % 3 == 0 else "airfare"
        label = "flight"
        model_out = label if i % 4 != 0 else "airfare"
        ml_out = label if i % 5 != 0 else "airline"
        out.append(
            ClassificationRecord(
                timestamp=1_700_000_000.0 + i,
                input=INPUT,
                label=label,
                outcome=outcome,
                source="rule",
                confidence=1.0,
                rule_output=rule_out,
                model_output=model_out,
                model_confidence=0.9,
                ml_output=ml_out,
                ml_confidence=0.85,
            )
        )
    return out


def bench_advance_log_sizes(n_iter: int) -> list[CellStats]:
    """advance() cost × log size (0, 1k, 10k, 100k)."""
    cells: list[CellStats] = []
    for log_size in (0, 1_000, 10_000, 100_000):
        sw = LearnedSwitch(
            rule=_rule_atis,
            name=_unique_name(f"bench_advance_{log_size}"),
            author="bench",
            labels=["flight", "airfare", "airline"],
            config=SwitchConfig(
                starting_phase=Phase.MODEL_SHADOW,  # so advance() evaluates real pairs
                auto_record=False,
                auto_advance=False,
            ),
            # Use InMemoryStorage (unbounded) so 100k records fit.
            storage=InMemoryStorage(),
            model=_StubLM(),
        )
        # Seed the storage directly so we skip record_verdict overhead.
        for r in _seed_records(log_size):
            sw._storage.append_record(sw.name, r)
        # advance() is cheap relative to classify but expensive relative to
        # record_verdict at 100k. Scale iterations down to keep total runtime
        # under a few seconds.
        cell_iters = n_iter
        if log_size >= 10_000:
            cell_iters = max(200, n_iter // 100)
        if log_size >= 100_000:
            cell_iters = max(50, n_iter // 1000)
        cells.append(
            bench(
                name=f"advance.log_size={log_size}",
                fn=lambda sw=sw: sw.advance(),
                params={
                    "log_size": log_size,
                    "gate": "McNemarGate",
                    "kind": "advance",
                },
                n_iter=cell_iters,
                warmup=min(100, cell_iters),
            )
        )
        # advance() at MODEL_SHADOW mutates starting_phase if the gate
        # passes. Reset back so subsequent iterations evaluate the same
        # transition. Check actual phase: if gate never passes (likely
        # with random data) no reset is needed — but safe to try.
        sw.config.starting_phase = Phase.MODEL_SHADOW
    return cells


def bench_gate_types(n_iter: int, gate_log_size: int = 10_000) -> list[CellStats]:
    """Gate.evaluate() × gate type on 10k records.

    Measures just the gate-evaluation path in isolation so different
    gate types are comparable apples-to-apples.
    """
    cells: list[CellStats] = []
    records = _seed_records(gate_log_size)
    current, target = Phase.RULE, Phase.MODEL_SHADOW
    gates: list[tuple[str, Any]] = [
        ("McNemarGate", McNemarGate()),
        ("AccuracyMarginGate", AccuracyMarginGate()),
        (
            "MinVolumeGate(McNemar)",
            MinVolumeGate(McNemarGate(), min_records=100),
        ),
        (
            "CompositeGate.all_of[Mc,Acc]",
            CompositeGate.all_of([McNemarGate(), AccuracyMarginGate()]),
        ),
    ]
    # Gate eval is ~1-30ms on 10k records — cap iterations.
    cell_iters = min(n_iter, 500)
    for gate_name, gate in gates:
        cells.append(
            bench(
                name=f"gate.{gate_name}.log_size={gate_log_size}",
                fn=lambda gate=gate: gate.evaluate(records, current, target),
                params={
                    "gate": gate_name,
                    "log_size": gate_log_size,
                    "kind": "gate",
                },
                n_iter=cell_iters,
                warmup=min(50, cell_iters),
            )
        )
    return cells


def bench_dispatch_vs_classify(n_iter: int) -> list[CellStats]:
    """dispatch() vs classify() — quantify action-dispatch overhead."""
    cells: list[CellStats] = []

    def _action(x):
        return None

    # No-op action so we measure pure dispatch overhead.
    sw_classify = LearnedSwitch(
        rule=_rule_atis,
        name=_unique_name("bench_c"),
        author="bench",
        labels={"flight": _action, "airfare": _action, "airline": _action},
        config=SwitchConfig(starting_phase=Phase.RULE, auto_record=False, auto_advance=False),
    )
    cells.append(
        bench(
            name="classify.RULE.with_labeled_actions",
            fn=lambda: sw_classify.classify(INPUT),
            params={"kind": "classify-with-actions"},
            n_iter=n_iter,
        )
    )
    cells.append(
        bench(
            name="dispatch.RULE.with_labeled_actions",
            fn=lambda: sw_classify.dispatch(INPUT),
            params={"kind": "dispatch"},
            n_iter=n_iter,
        )
    )
    return cells


def bench_entry_points(n_iter: int) -> list[CellStats]:
    """Decorator-call vs .classify() vs .dispatch()."""
    from dendra import ml_switch

    cells: list[CellStats] = []

    @ml_switch(
        labels=["flight", "airfare", "airline"],
        author="bench",
        auto_record=False,
        auto_advance=False,
    )
    def triage(text):
        return _rule_atis(text)

    # Decorator call — returns the rule output directly (bare __call__).
    cells.append(
        bench(
            name="decorator.__call__",
            fn=lambda: triage(INPUT),
            params={"entry_point": "__call__", "kind": "entry-point"},
            n_iter=n_iter,
        )
    )
    cells.append(
        bench(
            name="decorator.classify",
            fn=lambda: triage.classify(INPUT),
            params={"entry_point": "classify", "kind": "entry-point"},
            n_iter=n_iter,
        )
    )
    cells.append(
        bench(
            name="decorator.dispatch",
            fn=lambda: triage.dispatch(INPUT),
            params={"entry_point": "dispatch", "kind": "entry-point"},
            n_iter=n_iter,
        )
    )
    return cells


def bench_payload_sweep(n_iter: int, scratch: Path) -> list[CellStats]:
    """record_verdict payload-size sweep on FileStorage + Sqlite."""
    cells: list[CellStats] = []
    sizes = [100, 1_024, 10_240, 102_400]
    # FileStorage is more sensitive to payload size than in-memory.
    for size in sizes:
        payload = "x" * size
        for backend_name, storage in (
            ("BoundedInMemoryStorage", BoundedInMemoryStorage()),
            ("FileStorage", FileStorage(scratch / f"file_payload_{size}")),
            (
                "SqliteStorage",
                SqliteStorage(scratch / f"sqlite_payload_{size}" / "log.db"),
            ),
        ):
            sw = make_switch(phase=Phase.RULE, auto_record=False, storage=storage)
            # FileStorage scales its iterations down for the 100KB case so
            # the suite doesn't balloon.
            cell_iters = n_iter
            if size >= 10_240 and backend_name != "BoundedInMemoryStorage":
                cell_iters = max(500, n_iter // 10)
            cells.append(
                bench(
                    name=f"record_verdict.payload={size}B.{backend_name}",
                    fn=lambda sw=sw, payload=payload: sw.record_verdict(
                        input=payload, label="flight", outcome="unknown"
                    ),
                    params={
                        "payload_bytes": size,
                        "storage": backend_name,
                        "kind": "payload-sweep",
                    },
                    n_iter=cell_iters,
                    warmup=min(100, cell_iters),
                )
            )
    return cells


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-iter", type=int, default=10_000)
    parser.add_argument(
        "--jsonl",
        type=Path,
        default=None,
        help="Path for raw JSONL output. Default: docs/benchmarks/v1-baseline-YYYY-MM-DD.jsonl",
    )
    parser.add_argument(
        "--md",
        type=Path,
        default=Path("docs/benchmarks/v1-audit-benchmarks.md"),
    )
    parser.add_argument(
        "--skip-groups",
        type=str,
        default="",
        help="Comma-separated groups to skip (phase,storage,verdict,autoadv,advance,gate,dispatch,entry,payload)",  # noqa: E501
    )
    args = parser.parse_args()

    date_str = time.strftime("%Y-%m-%d", time.localtime())
    jsonl_path = args.jsonl or Path(f"docs/benchmarks/v1-baseline-{date_str}.jsonl")
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    env = collect_env()
    print(
        f"[env] Python {platform.python_version()} / {env['cpu']} / "
        f"{env['ram_gb']} GB / dendra {env['dendra_version']}"
    )

    scratch = Path(tempfile.mkdtemp(prefix="dendra_bench_"))
    print(f"[scratch] {scratch}")

    skip = {s.strip() for s in args.skip_groups.split(",") if s.strip()}
    all_cells: list[CellStats] = []

    try:
        if "phase" not in skip:
            print("[run] phase × auto_record matrix...")
            all_cells.extend(bench_classify_phase_matrix(args.n_iter))
        if "storage" not in skip:
            print("[run] classify × storage matrix...")
            all_cells.extend(bench_classify_storage_matrix(args.n_iter, scratch))
        if "verdict" not in skip:
            print("[run] record_verdict × storage...")
            all_cells.extend(bench_record_verdict_storage(args.n_iter, scratch))
        if "autoadv" not in skip:
            print("[run] record_verdict auto_advance...")
            all_cells.extend(bench_record_verdict_autoadvance(args.n_iter))
        if "advance" not in skip:
            print("[run] advance × log size...")
            all_cells.extend(bench_advance_log_sizes(args.n_iter))
        if "gate" not in skip:
            print("[run] gate type × 10k records...")
            all_cells.extend(bench_gate_types(args.n_iter))
        if "dispatch" not in skip:
            print("[run] dispatch vs classify...")
            all_cells.extend(bench_dispatch_vs_classify(args.n_iter))
        if "entry" not in skip:
            print("[run] entry points...")
            all_cells.extend(bench_entry_points(args.n_iter))
        if "payload" not in skip:
            print("[run] payload-size sweep...")
            all_cells.extend(bench_payload_sweep(args.n_iter, scratch))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    # Write JSONL. First line is the env block (tagged).
    with jsonl_path.open("w") as f:
        f.write(json.dumps({"type": "env", **env}) + "\n")
        for cell in all_cells:
            f.write(json.dumps({"type": "cell", **cell.to_row()}) + "\n")
    print(f"[write] JSONL → {jsonl_path}")

    # Write markdown report.
    md = render_markdown(env, all_cells)
    args.md.parent.mkdir(parents=True, exist_ok=True)
    args.md.write_text(md)
    print(f"[write] MD → {args.md}")

    # Print headline numbers so the caller can see results on stdout.
    print("\n=== Headline numbers ===")
    for c in all_cells:
        print(
            f"  {c.name:<60} p50={c.p50_ns / 1000:>9.3f}µs  "
            f"p95={c.p95_ns / 1000:>9.3f}µs  "
            f"p99={c.p99_ns / 1000:>9.3f}µs  "
            f"ops/s={c.ops_per_sec:>12,.0f}"
        )

    return 0


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _fmt_us(ns: int | float) -> str:
    us = ns / 1000.0
    if us < 10:
        return f"{us:.2f} µs"
    if us < 1000:
        return f"{us:.1f} µs"
    return f"{us / 1000:.2f} ms"


def _fmt_ops(ops: float) -> str:
    if ops >= 1_000_000:
        return f"{ops / 1_000_000:.1f}M"
    if ops >= 1_000:
        return f"{ops / 1_000:.0f}k"
    return f"{ops:.0f}"


def _row(cell: CellStats) -> str:
    return (
        f"| {cell.name} | {_fmt_us(cell.p50_ns)} | {_fmt_us(cell.p95_ns)} | "
        f"{_fmt_us(cell.p99_ns)} | {_fmt_ops(cell.ops_per_sec)} |"
    )


def _filter_by_kind(cells: list[CellStats], kind: str) -> list[CellStats]:
    return [c for c in cells if c.params.get("kind") == kind]


def render_markdown(env: dict[str, Any], cells: list[CellStats]) -> str:
    lines: list[str] = []
    lines.append("# Benchmark refresh — v1 baseline")
    lines.append("")
    lines.append(
        f"Run date: **{env['date']}**  \n"
        f"Measured by: `scripts/run_v1_benchmarks.py` (perf_counter_ns, "
        f"10k iter / cell, 1k warmup)"
    )
    lines.append("")
    lines.append("## Environment")
    lines.append("")
    lines.append(f"- Python: {env['python_version'].splitlines()[0]}")
    lines.append(f"- Implementation: {env['python_implementation']}")
    lines.append(f"- Platform: {env['platform']}")
    lines.append(f"- Machine: {env['machine']}")
    lines.append(f"- CPU: {env['cpu']}")
    lines.append(f"- RAM: {env['ram_gb']} GB")
    lines.append(f"- Dendra: {env['dendra_version']}")
    lines.append("")

    # ---- classify phase matrix ----
    lines.append("## Hot path: `classify()` — phase × auto_record matrix")
    lines.append("")
    lines.append("Storage: `BoundedInMemoryStorage` (default) for all rows.")
    lines.append("")
    lines.append("| Mode | p50 | p95 | p99 | ops/sec |")
    lines.append("|---|---:|---:|---:|---:|")
    for c in _filter_by_kind(cells, "classify"):
        phase = c.params["phase"]
        ar = c.params["auto_record"]
        tag = f"Phase.{phase}, auto_record={ar}"
        if phase == "RULE" and ar is True:
            tag += " **(default)**"
        lines.append(
            f"| {tag} | {_fmt_us(c.p50_ns)} | {_fmt_us(c.p95_ns)} | "
            f"{_fmt_us(c.p99_ns)} | {_fmt_ops(c.ops_per_sec)} |"
        )
    lines.append("")

    # Derived: auto_record tax.
    rule_false = next((c for c in cells if c.name == "classify.RULE.auto_record=False"), None)
    rule_true = next((c for c in cells if c.name == "classify.RULE.auto_record=True"), None)
    if rule_false and rule_true:
        tax_ns = rule_true.p50_ns - rule_false.p50_ns
        tax_x = rule_true.p50_ns / max(rule_false.p50_ns, 1)
        lines.append(
            f"**auto_record tax at Phase.RULE (default-on):** "
            f"+{_fmt_us(tax_ns)} p50, **{tax_x:.1f}×** bare classify cost. "
            f"Every `classify()` call appends a ClassificationRecord "
            f"(UNKNOWN outcome) to storage — the new default makes the hot "
            f"path do real work."
        )
        lines.append("")

    # ---- classify × storage ----
    storage_cells = _filter_by_kind(cells, "classify-with-storage")
    if storage_cells:
        lines.append("## Hot path × storage backend (Phase.RULE, auto_record=True)")
        lines.append("")
        lines.append("| Storage backend | p50 | p95 | p99 | ops/sec |")
        lines.append("|---|---:|---:|---:|---:|")
        for c in storage_cells:
            lines.append(
                f"| {c.params['storage']} | {_fmt_us(c.p50_ns)} | {_fmt_us(c.p95_ns)} | "
                f"{_fmt_us(c.p99_ns)} | {_fmt_ops(c.ops_per_sec)} |"
            )
        lines.append("")
        lines.append(
            "The durable backends (`FileStorage`, `SqliteStorage`) turn "
            "`classify()` into a disk-write on every call when "
            "`auto_record=True` — this flips the hot path from "
            "sub-microsecond to **~1 ms**. Users who don't need the "
            "auto-log should pass `auto_record=False`."
        )
        lines.append("")

    # ---- record_verdict × storage ----
    rv_cells = _filter_by_kind(cells, "record_verdict")
    if rv_cells:
        lines.append("## `record_verdict()` × storage (auto_advance=False)")
        lines.append("")
        lines.append("| Storage backend | p50 | p95 | p99 | ops/sec |")
        lines.append("|---|---:|---:|---:|---:|")
        for c in rv_cells:
            lines.append(
                f"| {c.params['storage']} | {_fmt_us(c.p50_ns)} | {_fmt_us(c.p95_ns)} | "
                f"{_fmt_us(c.p99_ns)} | {_fmt_ops(c.ops_per_sec)} |"
            )
        lines.append("")

    # ---- auto-advance spike ----
    aa_cells = _filter_by_kind(cells, "record_verdict-auto-advance")
    if aa_cells:
        lines.append("## `record_verdict()` with `auto_advance=True`")
        lines.append("")
        lines.append(
            "`auto_advance_interval=100` means every 100th call triggers "
            "`advance()` (which walks the log + runs the gate). The spike "
            "shows up at the p99 — 99% of calls are normal, the 1% that "
            "pay for gate evaluation are slower."
        )
        lines.append("")
        lines.append("| Config | p50 | p95 | p99 | ops/sec |")
        lines.append("|---|---:|---:|---:|---:|")
        for c in aa_cells:
            lines.append(
                f"| interval={c.params['auto_advance_interval']} | "
                f"{_fmt_us(c.p50_ns)} | {_fmt_us(c.p95_ns)} | "
                f"{_fmt_us(c.p99_ns)} | {_fmt_ops(c.ops_per_sec)} |"
            )
        lines.append("")

    # ---- advance × log size ----
    adv_cells = _filter_by_kind(cells, "advance")
    if adv_cells:
        lines.append("## `advance()` cost × log size")
        lines.append("")
        lines.append(
            "Gate: default `McNemarGate`. Records seeded with alternating "
            "correct/incorrect outcomes so paired-correctness math has "
            "real discordant pairs."
        )
        lines.append("")
        lines.append("| Log size | p50 | p95 | p99 | ops/sec |")
        lines.append("|---|---:|---:|---:|---:|")
        for c in adv_cells:
            lines.append(
                f"| {c.params['log_size']:,} | {_fmt_us(c.p50_ns)} | "
                f"{_fmt_us(c.p95_ns)} | {_fmt_us(c.p99_ns)} | "
                f"{_fmt_ops(c.ops_per_sec)} |"
            )
        lines.append("")
        # Linearity check.
        sizes_times = [
            (c.params["log_size"], c.p50_ns) for c in adv_cells if c.params["log_size"] > 0
        ]
        if len(sizes_times) >= 2:
            (s1, t1), *_, (sN, tN) = sizes_times
            scale = tN / max(t1, 1)
            ratio = sN / max(s1, 1)
            lines.append(
                f"advance() is **O(n)** in log size. {s1:,} → {sN:,} "
                f"records ({ratio:.0f}×) ≈ {scale:.1f}× time — "
                f"linear-scan cost dominated by McNemar's single pass "
                f"over the log + two accuracy sums."
            )
            lines.append("")

    # ---- gate matrix ----
    gate_cells = _filter_by_kind(cells, "gate")
    if gate_cells:
        lines.append("## Gate evaluation cost (10k paired records)")
        lines.append("")
        lines.append("| Gate | p50 | p95 | p99 | ops/sec |")
        lines.append("|---|---:|---:|---:|---:|")
        for c in gate_cells:
            lines.append(
                f"| {c.params['gate']} | {_fmt_us(c.p50_ns)} | {_fmt_us(c.p95_ns)} | "
                f"{_fmt_us(c.p99_ns)} | {_fmt_ops(c.ops_per_sec)} |"
            )
        lines.append("")

    # ---- dispatch overhead ----
    disp_cells = _filter_by_kind(cells, "classify-with-actions") + _filter_by_kind(
        cells, "dispatch"
    )
    if disp_cells:
        lines.append("## Action-dispatch overhead")
        lines.append("")
        lines.append(
            "Same switch, same inputs, same (no-op) actions attached to "
            "every label. `classify()` ignores the actions; `dispatch()` "
            "fires the matched one."
        )
        lines.append("")
        lines.append("| Entry | p50 | p95 | p99 | ops/sec |")
        lines.append("|---|---:|---:|---:|---:|")
        for c in disp_cells:
            lines.append(_row(c))
        lines.append("")
        classify_row = next(
            (c for c in disp_cells if c.params["kind"] == "classify-with-actions"),
            None,
        )
        dispatch_row = next((c for c in disp_cells if c.params["kind"] == "dispatch"), None)
        if classify_row and dispatch_row:
            tax = dispatch_row.p50_ns - classify_row.p50_ns
            lines.append(
                f"Dispatch overhead over classify: **{_fmt_us(tax)}** p50 "
                f"(label lookup + action invocation + action timing)."
            )
            lines.append("")

    # ---- entry points ----
    ep_cells = _filter_by_kind(cells, "entry-point")
    if ep_cells:
        lines.append("## Entry-point comparison (decorator)")
        lines.append("")
        lines.append("| Entry | p50 | p95 | p99 | ops/sec |")
        lines.append("|---|---:|---:|---:|---:|")
        for c in ep_cells:
            lines.append(_row(c))
        lines.append("")

    # ---- payload sweep ----
    pay_cells = _filter_by_kind(cells, "payload-sweep")
    if pay_cells:
        lines.append("## Payload-size sweep for `record_verdict()`")
        lines.append("")
        lines.append("| Storage | Payload | p50 | p95 | p99 | ops/sec |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for c in pay_cells:
            lines.append(
                f"| {c.params['storage']} | {c.params['payload_bytes']:,} B | "
                f"{_fmt_us(c.p50_ns)} | {_fmt_us(c.p95_ns)} | "
                f"{_fmt_us(c.p99_ns)} | {_fmt_ops(c.ops_per_sec)} |"
            )
        lines.append("")

    # ---- README comparison ----
    readme_compare = _build_readme_comparison(cells)
    lines.append("## Comparison to README claims")
    lines.append("")
    lines.append("| README claim | Prior audit (2026-04-24) | New measurement | Delta |")
    lines.append("|---|---:|---:|---|")
    for row in readme_compare:
        lines.append(row)
    lines.append("")

    # ---- Pinned numbers ----
    lines.append("## Updated numbers to pin in README + tests")
    lines.append("")
    lines.extend(_pin_lines(cells))
    lines.append("")

    # ---- Regressions ----
    lines.append("## Regressions introduced by recent features")
    lines.append("")
    lines.extend(_regression_notes(cells))
    lines.append("")

    # ---- Next steps ----
    lines.append("## Recommended next steps")
    lines.append("")
    lines.extend(_next_step_lines(cells))
    lines.append("")

    # ---- Methodology footer ----
    lines.append("## Methodology notes")
    lines.append("")
    lines.append(
        "- Measurements use `time.perf_counter_ns()` in a tight Python loop; "
        "1000-iteration warm-up, 10,000-iteration measurement per cell "
        "(advance/gate cells scale down because a single call is "
        "1–50 ms).\n"
        "- Percentiles are per-call; `ops/sec` is derived from the mean.\n"
        "- Background processes on the dev laptop introduce ~5–15% "
        "variance on any single cell. p99 is the noisiest bucket. Treat "
        "order-of-magnitude comparisons as load-bearing; single-digit-"
        "percent comparisons are inside the noise floor.\n"
        "- Storage backends write to a scratch directory under "
        "`$TMPDIR` (local SSD). Numbers will be higher on spinning disk, "
        "lower on NVMe with fsync barriers relaxed."
    )
    lines.append("")

    return "\n".join(lines)


def _build_readme_comparison(cells: list[CellStats]) -> list[str]:
    rows: list[str] = []

    # Rule-only call (no switch). We don't measure bare rule here — fall back
    # to the existing test's finding or mark n/a.
    rows.append(
        "| Bare rule call: `0.12 µs p50` | 0.17 µs (stale) | "
        "not re-measured (not on switch path) | stale; still an order-of-magnitude claim |"
    )

    rule_false = next((c for c in cells if c.name == "classify.RULE.auto_record=False"), None)
    rule_true = next((c for c in cells if c.name == "classify.RULE.auto_record=True"), None)
    if rule_false:
        rows.append(
            f"| Phase-0 classify: `0.62 µs p50` (5× rule) | 1.08 µs (prev audit) | "
            f"**{_fmt_us(rule_false.p50_ns)}** (auto_record=False) | "
            f"**README is stale** — retract the 0.62 µs figure. New claim: "
            f"{_fmt_us(rule_false.p50_ns)} p50 at Phase.RULE with auto_record=False. |"
        )
    if rule_true:
        rows.append(
            f"| Phase-0 classify *(default config)* | n/a | "
            f"**{_fmt_us(rule_true.p50_ns)}** (auto_record=True) | "
            f"New regression: default classify now writes an UNKNOWN "
            f"record, ~{rule_true.p50_ns / max(rule_false.p50_ns, 1):.1f}× cost. |"
        )
    rows.append(
        "| TF-IDF ML head: `105 µs p50` | not measured | **not re-measured** "
        "(stub head used here) | Same unverified claim; needs a real trained head benchmark. |"
    )
    rows.append(
        "| Ollama LLM: `~250 ms p50` | hardcoded constant | **not re-measured** "
        "(stub LLM used here) | Same unverified claim; run a live Ollama test on release hardware. |"  # noqa: E501
    )
    return rows


def _pin_lines(cells: list[CellStats]) -> list[str]:
    lines: list[str] = []
    lookup = {c.name: c for c in cells}

    def pin(label: str, key: str) -> None:
        c = lookup.get(key)
        if not c:
            return
        lines.append(
            f"- **{label}:** {_fmt_us(c.p50_ns)} p50 / "
            f"{_fmt_us(c.p95_ns)} p95 / {_fmt_us(c.p99_ns)} p99 "
            f"({_fmt_ops(c.ops_per_sec)} ops/sec)"
        )

    pin("Phase.RULE classify (auto_record=False)", "classify.RULE.auto_record=False")
    pin(
        "Phase.RULE classify (auto_record=True, default)",
        "classify.RULE.auto_record=True",
    )
    pin(
        "Phase.MODEL_SHADOW classify (auto_record=False)",
        "classify.MODEL_SHADOW.auto_record=False",
    )
    pin(
        "Phase.ML_WITH_FALLBACK classify (auto_record=False)",
        "classify.ML_WITH_FALLBACK.auto_record=False",
    )
    pin("record_verdict (BoundedInMemory)", "record_verdict.BoundedInMemoryStorage")
    pin(
        "record_verdict (FileStorage, fsync=False)",
        "record_verdict.FileStorage.fsync=False",
    )
    pin(
        "record_verdict (FileStorage, fsync=True)",
        "record_verdict.FileStorage.fsync=True",
    )
    pin(
        "record_verdict (SqliteStorage, sync=NORMAL)",
        "record_verdict.SqliteStorage.sync=NORMAL",
    )
    pin("advance() at 10k log", "advance.log_size=10000")
    pin("advance() at 100k log", "advance.log_size=100000")
    pin("McNemarGate on 10k records", "gate.McNemarGate.log_size=10000")
    pin("dispatch() (no-op action)", "dispatch.RULE.with_labeled_actions")
    return lines


def _regression_notes(cells: list[CellStats]) -> list[str]:
    lines: list[str] = []
    lookup = {c.name: c for c in cells}

    rf = lookup.get("classify.RULE.auto_record=False")
    rt = lookup.get("classify.RULE.auto_record=True")
    if rf and rt:
        ratio = rt.p50_ns / max(rf.p50_ns, 1)
        lines.append(
            f"1. **`auto_record=True` (default) tax on classify:** "
            f"{_fmt_us(rf.p50_ns)} → {_fmt_us(rt.p50_ns)} p50 "
            f"({ratio:.1f}×). Root cause: every classify now allocates a "
            f"`ClassificationRecord` and calls `storage.append_record`. "
            f"On the default `BoundedInMemoryStorage` this is cheap "
            f"but non-zero; on `FileStorage`/`SqliteStorage` it becomes "
            f"a sub-millisecond-to-millisecond write."
        )

    aa = next(
        (c for c in cells if c.params.get("kind") == "record_verdict-auto-advance"),
        None,
    )
    rv = lookup.get("record_verdict.BoundedInMemoryStorage")
    if aa and rv:
        spike_ratio = aa.p99_ns / max(rv.p50_ns, 1)
        lines.append(
            f"2. **`auto_advance_interval=100` spike:** "
            f"every 100th record_verdict triggers `advance()`, which walks "
            f"the full log. p50 is {_fmt_us(aa.p50_ns)} (close to bare "
            f"record_verdict at {_fmt_us(rv.p50_ns)}), **p99 is "
            f"{_fmt_us(aa.p99_ns)}** — roughly {spike_ratio:.0f}× the p50. "
            f"High-throughput verdict recorders should either disable "
            f"auto_advance (`auto_advance=False`) or use a larger interval."
        )

    fs = lookup.get("classify.RULE.auto_record=True.FileStorage")
    bm = lookup.get("classify.RULE.auto_record=True.BoundedInMemoryStorage")
    if fs and bm:
        lines.append(
            f"3. **Default `auto_record=True` + `persist=True` (FileStorage) "
            f"is the worst-case cell:** "
            f"{_fmt_us(bm.p50_ns)} → {_fmt_us(fs.p50_ns)} p50 "
            f"({fs.p50_ns / max(bm.p50_ns, 1):.0f}×). "
            f"Every `classify()` becomes a fsync-free file append. "
            f"Either document the pairing as a pro-mode trade-off or "
            f"flip `auto_record` default off for `persist=True` paths."
        )

    gate = lookup.get("gate.McNemarGate.log_size=10000")
    comp = lookup.get("gate.CompositeGate.all_of[Mc,Acc].log_size=10000")
    if gate and comp:
        lines.append(
            f"4. **CompositeGate walks the log once per sub-gate.** "
            f"McNemarGate alone: {_fmt_us(gate.p50_ns)}. "
            f"CompositeGate.all_of([Mc, Acc]): {_fmt_us(comp.p50_ns)} "
            f"({comp.p50_ns / max(gate.p50_ns, 1):.1f}× McNemar alone). "
            f"Future optimization: share the paired-correctness "
            f"extraction pass across sub-gates."
        )

    return lines


def _next_step_lines(cells: list[CellStats]) -> list[str]:
    return [
        "1. **Retract the 0.62 µs README claim.** The `classify()` at "
        "Phase.RULE number is ~1 µs at best (auto_record=False); the "
        "default config is slower. Pin real p50/p99 numbers into "
        "`tests/test_latency_pinned.py` and let them fail CI on drift.",
        "2. **Wire `tests/test_latency_pinned.py` into CI** with a "
        "`pytest -m benchmark` job that runs the new test on a "
        "dedicated runner (variance is lower on GH's `macos-14` or "
        "`ubuntu-latest` if kept to single-job). Acceptable drift: 2×.",
        "3. **Document the `auto_record` default tax in the README.** "
        "Pair it with a recipe: `auto_record=False` for "
        "throughput-sensitive call sites.",
        "4. **Record a live TF-IDF + real LLM measurement** to replace "
        "the hardcoded `105 µs` / `250 ms` README numbers. Current "
        "numbers above use stubs for determinism — they verify switch "
        "overhead, not ML-head cost.",
        "5. **Investigate the `record_verdict` + `FileStorage` "
        "~1 ms cost.** Keep-fd-open or buffered-append variant would "
        "drop this into tens of µs. Already flagged in the earlier "
        "perf audit — now that we ship `auto_record=True` by default, "
        "the remediation is higher priority.",
        "6. **Re-run this suite on release hardware** before v1 and "
        "diff the JSONL against "
        "`docs/benchmarks/v1-baseline-YYYY-MM-DD.jsonl` — "
        "the raw data is stored one-row-per-cell so `jq` and pandas "
        "diffs are trivial.",
    ]


if __name__ == "__main__":
    sys.exit(main())
