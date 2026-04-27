#!/usr/bin/env python3
"""Enrich landing/data/analyze-*.json with source snippets per site.

For each detected classification site (top N by fit_score), reads the
cloned source file from /tmp/dendra-corpus/<repo>/<file_path> and
captures lines [line_start - 3, line_end + 3] as `source_snippet`.
Also captures repo-level metadata (default branch, raw URL prefix)
so the landing UI can deep-link to GitHub.

Also filters out test-suite false positives. A site is dropped if any of:

  1. Function name matches ``^test_`` (pytest convention).
  2. File path contains ``/tests/``, ``/test/``, ``_test.py``, ``test_``,
     or ``/conftest.py``.
  3. Function name is a unittest fixture method
     (``setUp``, ``tearDown``, ``setUpClass``, ``tearDownClass``,
     ``setUpModule``, ``tearDownModule``).
  4. Function takes zero arguments AND has no ``return`` statements
     (sequential side-effect script, almost certainly not a classifier).

Run from repo root:
    python3 scripts/enrich_landing_corpus.py
"""
from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

# Make ``src/`` importable so we can drive the analyzer programmatically.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from dendra.analyzer import analyze  # noqa: E402

LANDING_DATA = _REPO_ROOT / "landing" / "data"
CORPUS_ROOT = Path("/tmp/dendra-corpus")

# (preset slug, github org/repo, default branch). Used to build raw.githubusercontent
# URLs so the UI can deep-link to the actual file at the line.
REPOS = {
    "fastapi":  ("tiangolo/fastapi",     "master"),
    "requests": ("psf/requests",         "main"),
    "dvc":      ("iterative/dvc",        "main"),
    "marimo":   ("marimo-team/marimo",   "main"),
}

ENRICH_TOP_N = 15  # match the UI's row cap with a buffer
CONTEXT_BEFORE = 8
CONTEXT_AFTER = 12

# ---------------------------------------------------------------------------
# Test-function filter
# ---------------------------------------------------------------------------

_TEST_NAME_RE = re.compile(r"^test_")
_UNITTEST_FIXTURE_NAMES = frozenset({
    "setUp",
    "tearDown",
    "setUpClass",
    "tearDownClass",
    "setUpModule",
    "tearDownModule",
})
_TEST_PATH_FRAGMENTS = ("/tests/", "/test/", "_test.py", "test_", "/conftest.py")


def _path_looks_like_test(file_path: str) -> bool:
    """True if ``file_path`` is part of a test suite."""
    # Normalize so prefixed-tests/ matches /tests/.
    normalized = "/" + file_path.replace("\\", "/").lstrip("/")
    return any(frag in normalized for frag in _TEST_PATH_FRAGMENTS)


def _name_looks_like_test(function_name: str) -> bool:
    if _TEST_NAME_RE.match(function_name):
        return True
    if function_name in _UNITTEST_FIXTURE_NAMES:
        return True
    return False


def _is_zero_arg_no_return(repo_root: Path, site: dict) -> bool:
    """True if the site's function takes no args AND has no return statements.

    Returns False on any read/parse failure (we err toward keeping the site).
    """
    rel_path = site.get("file_path")
    fn_name = site.get("function_name")
    line_start = site.get("line_start")
    if not rel_path or not fn_name or line_start is None:
        return False
    full_path = repo_root / rel_path
    try:
        source = full_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if node.name != fn_name:
            continue
        if node.lineno != line_start:
            continue
        # Count *all* parameter slots (positional, keyword-only, *args, **kwargs).
        a = node.args
        total_args = (
            len(a.posonlyargs)
            + len(a.args)
            + len(a.kwonlyargs)
            + (1 if a.vararg else 0)
            + (1 if a.kwarg else 0)
        )
        if total_args != 0:
            return False
        for inner in ast.walk(node):
            if isinstance(inner, ast.Return):
                return False
        return True
    return False


def _site_is_test(site: dict, repo_root: Path) -> tuple[bool, str]:
    """Return (filter_out, reason) for one site."""
    file_path = site.get("file_path", "")
    fn_name = site.get("function_name", "")
    if _name_looks_like_test(fn_name):
        return True, "name"
    if _path_looks_like_test(file_path):
        return True, "path"
    if _is_zero_arg_no_return(repo_root, site):
        return True, "zero-arg-no-return"
    return False, ""


def filter_test_sites(
    sites: list[dict],
    repo_root: Path,
    *,
    slug: str,
) -> tuple[list[dict], dict[str, int]]:
    """Drop test-suite sites. Return (kept, counts_by_reason)."""
    kept: list[dict] = []
    counts = {"name": 0, "path": 0, "zero-arg-no-return": 0}
    for site in sites:
        is_test, reason = _site_is_test(site, repo_root)
        if is_test:
            counts[reason] += 1
            continue
        kept.append(site)
    total = sum(counts.values())
    if total:
        breakdown = ", ".join(f"{k}={v}" for k, v in counts.items() if v)
        print(
            f"  {slug}: filtered {total} test sites ({breakdown})",
            file=sys.stderr,
        )
    return kept, counts


# ---------------------------------------------------------------------------
# Snippet extraction
# ---------------------------------------------------------------------------


def extract_snippet(file_path: Path, line_start: int, line_end: int) -> dict | None:
    """Return {snippet, snippet_start_line} for a site, or None on failure."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, ValueError):
        return None
    lines = text.splitlines()
    n = len(lines)
    snippet_start = max(1, line_start - CONTEXT_BEFORE)
    snippet_end = min(n, line_end + CONTEXT_AFTER)
    snippet = "\n".join(lines[snippet_start - 1:snippet_end])
    return {
        "snippet": snippet,
        "snippet_start_line": snippet_start,
        "snippet_end_line": snippet_end,
    }


def _run_analyzer(repo_root: Path) -> dict:
    """Run the static analyzer and return a serialized report dict.

    Mirrors the JSON shape that ``dendra analyze --format json`` emits
    so downstream code (and the landing UI) sees the same fields.
    """
    report = analyze(repo_root)
    return {
        "root": report.root,
        "files_scanned": report.files_scanned,
        "total_sites": report.total_sites(),
        "sites": [asdict(s) for s in report.by_score_desc()],
        "errors": report.errors,
    }


def enrich_one(slug: str, gh_path: str, branch: str) -> int:
    json_path = LANDING_DATA / f"analyze-{slug}.json"
    repo_root = CORPUS_ROOT / slug
    if not repo_root.exists():
        print(f"  skip {slug}: no clone at {repo_root}")
        return 0

    # Always regenerate from the cloned source so newly-added analyzer
    # patterns are reflected, then layer the test-suite filter on top.
    data = _run_analyzer(repo_root)
    data["repo_label"] = slug
    data["github_path"] = gh_path
    data["github_branch"] = branch
    data["raw_url_prefix"] = f"https://raw.githubusercontent.com/{gh_path}/{branch}"
    data["github_blob_prefix"] = f"https://github.com/{gh_path}/blob/{branch}"

    sites = data.get("sites", [])
    pre_filter = len(sites)
    sites, _counts = filter_test_sites(sites, repo_root, slug=slug)
    post_filter = len(sites)

    sites_sorted = sorted(sites, key=lambda s: s["fit_score"], reverse=True)
    enriched = 0

    for site in sites_sorted[:ENRICH_TOP_N]:
        rel_path = site["file_path"]
        full_path = repo_root / rel_path
        snippet_info = extract_snippet(full_path, site["line_start"], site["line_end"])
        if snippet_info:
            site.update(snippet_info)
            enriched += 1

    # Sort sites back by fit_score so the JSON order matches what UI expects.
    data["sites"] = sites_sorted
    data["total_sites"] = post_filter

    json_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(
        f"  {slug}: {enriched}/{min(post_filter, ENRICH_TOP_N)} top sites enriched "
        f"({pre_filter} -> {post_filter} after test filter)"
    )
    return enriched


def main() -> int:
    print(f"Enriching corpus in {LANDING_DATA}")
    total = 0
    for slug, (gh_path, branch) in REPOS.items():
        total += enrich_one(slug, gh_path, branch)
    print(f"Done: {total} sites enriched across {len(REPOS)} repos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
