#!/usr/bin/env python
# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0
"""Profile FileStorage under 4-thread concurrent write workload.

Captures the cProfile output (sorted by cumulative time) to
``tests/perf/profiles/filestorage_4thread.txt`` so the bottleneck is
attributable per call site. Issue #136.
"""

from __future__ import annotations

import cProfile
import io
import pstats
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dendra import ClassificationRecord, FileStorage  # noqa: E402


def _record() -> ClassificationRecord:
    return ClassificationRecord(
        timestamp=time.time(),
        input="hello",
        label="a",
        outcome="unknown",
        source="rule",
        confidence=1.0,
    )


def run_workload(fs: FileStorage, n_threads: int, ops_per_thread: int) -> tuple[int, float]:
    rec = _record()
    counts = [0] * n_threads
    barrier = threading.Barrier(n_threads + 1)

    def worker(idx: int) -> None:
        barrier.wait()
        for _ in range(ops_per_thread):
            fs.append_record(f"s{idx}", rec)
            counts[idx] += 1

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    barrier.wait()
    t0 = time.perf_counter()
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - t0
    return sum(counts), elapsed


def main() -> None:
    out_path = ROOT / "tests" / "perf" / "profiles" / "filestorage_4thread.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    n_threads = 4
    ops_per_thread = 10_000

    with tempfile.TemporaryDirectory() as tmp:
        fs = FileStorage(Path(tmp) / "fs", batching=False)
        # Warmup so file creation cost is not in the profile.
        for _ in range(500):
            fs.append_record("warmup", _record())

        profiler = cProfile.Profile()
        profiler.enable()
        total, elapsed = run_workload(fs, n_threads, ops_per_thread)
        profiler.disable()

        fs.close()

    rate = total / elapsed
    buf = io.StringIO()
    ps = pstats.Stats(profiler, stream=buf).sort_stats("cumulative")
    buf.write(f"FileStorage(batching=False), N={n_threads} threads, {ops_per_thread} ops/thread\n")
    buf.write(f"Total ops: {total}; elapsed: {elapsed:.2f}s; rate: {rate:.0f} ops/s\n\n")
    ps.print_stats(40)
    buf.write("\n--- by tottime ---\n")
    pstats.Stats(profiler, stream=buf).sort_stats("tottime").print_stats(40)

    out_path.write_text(buf.getvalue())
    print(f"profile -> {out_path}")
    print(f"rate: {rate:.0f} ops/s")


if __name__ == "__main__":
    main()
