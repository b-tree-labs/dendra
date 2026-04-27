# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0

"""Fetch and vendor the codelangs benchmark dataset.

Clones each license-vetted upstream source (shallow), samples N files
per language, truncates each to ~50 lines, writes them under
``data/codelangs/<lang>/<idx>.txt``. Re-runnable; idempotent up to
upstream changes (commits are not pinned by default — pass
``--pin-commits`` and the script will note the resolved commit per
source in SOURCES.md).

Run from the repo root:
    python scripts/fetch_codelangs.py
"""

from __future__ import annotations

import hashlib
import subprocess
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data" / "codelangs"

# Per-source: enough metadata to reproduce + attribute. License notes
# are conservative (more permissive sources favored to keep our
# Apache 2.0 / BSL bundle clean).


@dataclass
class Source:
    lang: str
    repo: str
    license: str
    globs: list[str]
    n_samples: int = 60
    sub_path: str = ""  # restrict glob to this subdir
    notes: str = ""


SOURCES: list[Source] = [
    Source(
        lang="fortran",
        repo="https://github.com/njoy/NJOY2016.git",
        license="BSD-3 (LANL contributor variant)",
        globs=["src/**/*.f90", "src/**/*.F90", "src/**/*.f"],
        n_samples=40,
        notes=(
            "NJOY2016 is the FORTRAN nuclear data processing code (LANL). "
            "NJOY21 is the C++ rewrite, so we pull from NJOY2016 for "
            "authentic NE FORTRAN."
        ),
    ),
    Source(
        lang="fortran",
        repo="https://github.com/Reference-LAPACK/lapack.git",
        license="modified-BSD",
        globs=["SRC/**/*.f", "SRC/**/*.F", "BLAS/SRC/**/*.f"],
        n_samples=20,
        notes="Classical numerical FORTRAN, ubiquitous in scientific computing.",
    ),
    Source(
        lang="python",
        repo="https://github.com/python/cpython.git",
        license="PSF (redistributable with notice)",
        globs=["Lib/**/*.py"],
        n_samples=60,
        notes="CPython standard library; PSF-licensed.",
    ),
    Source(
        lang="javascript",
        repo="https://github.com/nodejs/node.git",
        license="MIT",
        globs=["lib/**/*.js"],
        n_samples=60,
        notes="Node.js standard library; MIT-licensed.",
    ),
    Source(
        lang="java",
        repo="https://github.com/apache/commons-lang.git",
        license="Apache-2.0",
        globs=["src/main/java/**/*.java"],
        n_samples=60,
    ),
    Source(
        lang="c",
        repo="https://github.com/curl/curl.git",
        license="curl-license (MIT-compatible)",
        globs=["lib/**/*.c", "src/**/*.c"],
        n_samples=60,
        notes=(
            "cURL — widely-deployed C with permissive license; "
            "chosen over GPL alternatives like glibc."
        ),
    ),
    Source(
        lang="cpp",
        repo="https://github.com/boostorg/algorithm.git",
        license="BSL-1.0",
        globs=["include/**/*.hpp", "include/**/*.h"],
        n_samples=60,
        notes="Boost.Algorithm; Boost Software License.",
    ),
    Source(
        lang="go",
        repo="https://github.com/golang/go.git",
        license="BSD-3-Clause",
        globs=["src/**/*.go"],
        n_samples=60,
    ),
    Source(
        lang="rust",
        repo="https://github.com/serde-rs/serde.git",
        license="MIT-OR-Apache-2.0",
        globs=["serde/src/**/*.rs", "serde_derive/src/**/*.rs"],
        n_samples=60,
        notes="serde over rust-lang/rust to keep clone size manageable.",
    ),
    Source(
        lang="ruby",
        repo="https://github.com/ruby/ruby.git",
        license="BSD-2-Clause",
        globs=["lib/**/*.rb"],
        n_samples=60,
    ),
    Source(
        lang="typescript",
        repo="https://github.com/microsoft/TypeScript.git",
        license="Apache-2.0",
        globs=["src/compiler/**/*.ts", "src/services/**/*.ts"],
        n_samples=60,
    ),
    Source(
        lang="kotlin",
        repo="https://github.com/JetBrains/kotlin.git",
        license="Apache-2.0",
        globs=[
            "compiler/frontend/src/**/*.kt",
            "compiler/util/src/**/*.kt",
            "libraries/stdlib/common/src/**/*.kt",
        ],
        n_samples=60,
    ),
    Source(
        lang="mojo",
        repo="https://github.com/modular/modular.git",
        license="Apache-2.0",
        globs=["mojo/**/*.mojo", "mojo/**/*.🔥", "**/*.mojo"],
        n_samples=60,
        notes="Modular's main repo (formerly modular/mojo); Mojo language source.",
    ),
]


def _shallow_clone(repo: str, dest: Path) -> str:
    """Shallow-clone to ``dest``; return the resolved HEAD commit."""
    subprocess.run(
        ["git", "clone", "--depth", "1", "--quiet", repo, str(dest)],
        check=True,
    )
    sha = subprocess.run(
        ["git", "-C", str(dest), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return sha


def _glob_files(root: Path, globs: Iterable[str]) -> list[Path]:
    seen: set[Path] = set()
    out: list[Path] = []
    for pattern in globs:
        for p in root.glob(pattern):
            if p.is_file() and p not in seen:
                seen.add(p)
                out.append(p)
    return out


def _truncate(text: str, max_lines: int = 50) -> str:
    lines = text.splitlines()
    return "\n".join(lines[:max_lines])


def _stable_pick(items: list[Path], n: int, seed: str) -> list[Path]:
    """Deterministic sample: rank by hash(seed + path)."""
    salted = [(hashlib.sha256(f"{seed}:{p}".encode()).hexdigest(), p) for p in items]
    salted.sort()
    return [p for _, p in salted[:n]]


def fetch_one(src: Source, out_root: Path, idx_offset: int = 0) -> tuple[int, str]:
    """Clone, sample, write. Returns (samples_written, head_sha)."""
    with tempfile.TemporaryDirectory(prefix="dendra-fetch-") as tmp:
        clone_path = Path(tmp) / "src"
        sha = _shallow_clone(src.repo, clone_path)
        candidates = _glob_files(clone_path, src.globs)
        picked = _stable_pick(candidates, src.n_samples, src.lang + ":" + src.repo)
        lang_dir = out_root / src.lang
        lang_dir.mkdir(parents=True, exist_ok=True)
        written = 0
        for i, path in enumerate(picked):
            try:
                text = path.read_text(errors="replace")
            except (OSError, UnicodeDecodeError):
                continue
            text = _truncate(text)
            if not text.strip():
                continue
            out_file = lang_dir / f"{idx_offset + i:04d}.txt"
            out_file.write_text(text)
            written += 1
        return written, sha


def main(argv: list[str] | None = None) -> int:
    import argparse

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    parser = argparse.ArgumentParser(description="Fetch codelangs corpus.")
    parser.add_argument(
        "--langs",
        nargs="+",
        default=None,
        help="Only fetch these language slugs (default: all configured sources).",
    )
    args = parser.parse_args(argv)

    sources = SOURCES
    if args.langs:
        wanted = set(args.langs)
        sources = [s for s in SOURCES if s.lang in wanted]

    # Track per-language file counts so multi-source langs (FORTRAN
    # uses NJOY2016 + LAPACK) don't overwrite each other.
    lang_offset: dict[str, int] = {}
    sha_log: list[tuple[Source, str]] = []

    for src in sources:
        offset = lang_offset.get(src.lang, 0)
        print(f"==> {src.lang} <- {src.repo} ({src.license})", flush=True)
        try:
            written, sha = fetch_one(src, DATA_DIR, idx_offset=offset)
        except subprocess.CalledProcessError as e:
            print(f"    SKIP: clone failed ({e.returncode}); continuing", flush=True)
            continue
        except Exception as e:
            print(f"    SKIP: {type(e).__name__}: {e}; continuing", flush=True)
            continue
        lang_offset[src.lang] = offset + written
        sha_log.append((src, sha))
        print(f"    wrote {written} files (head {sha[:12]})", flush=True)

    # Emit SOURCES.md provenance doc.
    sources_md = DATA_DIR / "SOURCES.md"
    lines = [
        "# Codelangs benchmark sources",
        "",
        "Code samples vendored from license-compatible upstream sources.",
        "Each language directory contains 50-line truncations of files",
        "sampled deterministically (`hash(lang + repo + path)`) so the",
        "fetch is reproducible up to upstream changes.",
        "",
        "Generated by `scripts/fetch_codelangs.py`. Re-run after upstream",
        "shifts; the SHA snapshot below pins the corpus to a known state.",
        "",
        "## Sources",
        "",
        "| Language | Repo | License | Files | HEAD at fetch |",
        "|---|---|---|---:|---|",
    ]
    for src, sha in sha_log:
        lines.append(
            f"| {src.lang} | {src.repo} | {src.license} | {src.n_samples} | `{sha[:12]}` |"
        )
    if any(s.notes for s, _ in sha_log):
        lines.extend(["", "## Notes", ""])
        for src, _ in sha_log:
            if src.notes:
                repo_name = src.repo.split("/")[-1].replace(".git", "")
                lines.append(f"- **{src.lang}** ({repo_name}): {src.notes}")
    sources_md.write_text("\n".join(lines) + "\n")
    print(f"\nWrote {sources_md.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
