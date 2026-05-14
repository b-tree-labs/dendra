#!/usr/bin/env python3
# Copyright (c) 2026 B-Tree Labs
# SPDX-License-Identifier: LicenseRef-BSL-1.1
"""Auto-lift sizing study.

Walks the local examples corpus plus (if present) the cloned
landing-analyzer corpora at /tmp/postrule-corpus/{fastapi,requests,dvc,
marimo}, runs `postrule.analyzer.analyze` to enumerate candidate
classification sites, and attempts both `lift_branches` and
`lift_evidence` on each site. Records per-site outcomes and emits

  - a JSON report at /tmp/postrule-sizing-study.json
  - a copy at docs/working/sizing-study-2026-04-27.json
  - a Markdown summary to stdout

The goal of this study (originally a Phase 2-5 gate, now retroactive)
is to tell us where to invest in v1.5: which refusal categories cost us
the most high-value sites, and what auto-lift coverage looks like
across real-world Python codebases.

This is a read-only diagnostic. No production code is touched.
"""

from __future__ import annotations

import ast
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Make sure the local src/ is importable when running directly.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))

from postrule.analyzer import (  # noqa: E402
    AnalyzerReport,
    LiftStatus,
    analyze,
)
from postrule.lifters.branch import LiftRefused, lift_branches  # noqa: E402
from postrule.lifters.evidence import lift_evidence  # noqa: E402

# ---------------------------------------------------------------------------
# Corpus discovery
# ---------------------------------------------------------------------------


@dataclass
class Corpus:
    name: str
    root: Path
    present: bool


def discover_corpora() -> list[Corpus]:
    out: list[Corpus] = [
        Corpus(name="examples", root=_REPO_ROOT / "examples", present=True),
    ]
    base = Path("/tmp/postrule-corpus")
    for sub in ("fastapi", "requests", "dvc", "marimo"):
        path = base / sub
        out.append(Corpus(name=sub, root=path, present=path.exists()))
    return out


# ---------------------------------------------------------------------------
# Per-site record
# ---------------------------------------------------------------------------


@dataclass
class SiteRecord:
    corpus: str
    file_path: str  # relative to corpus root
    function_name: str
    pattern: str
    line_start: int
    fit_score: float
    label_cardinality: int
    regime: str
    lift_status: str  # from analyzer
    hazards: list[dict] = field(default_factory=list)
    # Lifter outcomes
    branch_lift_status: str = "unknown"  # "success" | "refused" | "error"
    branch_lift_reason: str = ""
    branch_lift_category: str = ""
    evidence_lift_status: str = "unknown"
    evidence_lift_reason: str = ""
    evidence_lift_category: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_top_level_function_source(file_source: str, function_name: str) -> str | None:
    """Return source for ``function_name`` if it lives at the top level of
    ``file_source``, else None.

    The lifters operate on a module-level def. Functions defined inside
    classes or nested functions are out of scope for this sizing study,
    so we record those as 'nested' instead of attempting to lift them.
    Returning the file source unchanged when the def is at top level
    works too, since the lifters look up by name.
    """
    try:
        tree = ast.parse(file_source)
    except SyntaxError:
        return None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == function_name:
            return file_source
    return None


def _categorize_refusal(reason: str) -> str:
    """Coerce a LiftRefused.reason string into a stable category.

    Categories mirror the analyzer's hazard taxonomy where possible.
    """
    r = reason.lower()
    # Categories surfaced by the analyzer's hazard detectors.
    if r.startswith("not_a_classifier") or "zero-argument" in r or "not a classifier" in r:
        return "not_a_classifier"
    if r.startswith("eval_exec") or "eval" in r and "exec" in r:
        return "eval_exec"
    if r.startswith("dynamic_dispatch") or "getattr" in r or "dynamic dispatch" in r:
        return "dynamic_dispatch"
    if r.startswith("side_effect_evidence") or "side effect" in r or "side-effect" in r:
        return "side_effect_evidence"
    if r.startswith("multi_arg_no_annotation") or "annotation" in r:
        return "multi_arg_no_annotation"
    # Branch-lifter-specific structural refusals.
    if "shared mid-function state" in r or "mid-function state" in r:
        return "shared_state"
    if "no if/elif" in r or "no else branch" in r or "no default return" in r or "no wildcard" in r:
        return "missing_default"
    if "computed value" in r or "string-literal label" in r or "computed (non-literal)" in r:
        return "computed_return"
    if "try/except" in r:
        return "try_except_in_branch"
    if (
        "multiple top-level if" in r
        or "not a simple default return" in r
        or "unexpected statements" in r
    ):
        return "non_canonical_chain"
    if "match case with guard" in r:
        return "guarded_match"
    if "empty branch" in r or "empty match case" in r or "does not end in a return" in r:
        return "branch_no_return"
    if "function" in r and "not found" in r:
        return "not_found"
    return "other"


def _try_branch_lift(source: str, fn_name: str) -> tuple[str, str, str]:
    try:
        lift_branches(source, fn_name)
    except LiftRefused as e:
        return "refused", str(e.reason), _categorize_refusal(str(e.reason))
    except Exception as e:  # noqa: BLE001 - record, never crash the study
        return "error", f"{type(e).__name__}: {e}", "internal_error"
    return "success", "", ""


def _try_evidence_lift(source: str, fn_name: str) -> tuple[str, str, str]:
    try:
        lift_evidence(source, fn_name)
    except LiftRefused as e:
        return "refused", str(e.reason), _categorize_refusal(str(e.reason))
    except Exception as e:  # noqa: BLE001 - record, never crash
        return "error", f"{type(e).__name__}: {e}", "internal_error"
    return "success", "", ""


def _hazard_categories(hazards: list[dict]) -> list[str]:
    return [h.get("category", "") for h in hazards]


# ---------------------------------------------------------------------------
# Per-corpus sizing pass
# ---------------------------------------------------------------------------


def study_corpus(corpus: Corpus) -> list[SiteRecord]:
    if not corpus.present:
        return []
    report: AnalyzerReport = analyze(corpus.root)
    records: list[SiteRecord] = []

    # Cache per-file source text so we don't re-read for each site in
    # the same file.
    source_cache: dict[Path, str] = {}

    for site in report.sites:
        abs_path = (Path(report.root) / site.file_path).resolve()
        if abs_path not in source_cache:
            try:
                source_cache[abs_path] = abs_path.read_text(encoding="utf-8")
            except Exception as e:  # noqa: BLE001
                source_cache[abs_path] = ""
                # Skip this site; can't lift without source.
                records.append(
                    SiteRecord(
                        corpus=corpus.name,
                        file_path=site.file_path,
                        function_name=site.function_name,
                        pattern=site.pattern,
                        line_start=site.line_start,
                        fit_score=site.fit_score,
                        label_cardinality=site.label_cardinality,
                        regime=site.regime,
                        lift_status=site.lift_status,
                        hazards=[asdict(h) for h in site.hazards],
                        branch_lift_status="error",
                        branch_lift_reason=f"file read failed: {e}",
                        branch_lift_category="internal_error",
                        evidence_lift_status="error",
                        evidence_lift_reason=f"file read failed: {e}",
                        evidence_lift_category="internal_error",
                    )
                )
                continue

        source = source_cache[abs_path]
        # Lifters require a top-level def; if the analyzer found a
        # nested or method-level def with the same name, attempting to
        # lift it would cause a misleading 'not found' refusal. Record
        # those as nested rather than crashing.
        usable_source = _extract_top_level_function_source(source, site.function_name)

        if usable_source is None:
            records.append(
                SiteRecord(
                    corpus=corpus.name,
                    file_path=site.file_path,
                    function_name=site.function_name,
                    pattern=site.pattern,
                    line_start=site.line_start,
                    fit_score=site.fit_score,
                    label_cardinality=site.label_cardinality,
                    regime=site.regime,
                    lift_status=site.lift_status,
                    hazards=[asdict(h) for h in site.hazards],
                    branch_lift_status="refused",
                    branch_lift_reason="function not at module top level (nested or method)",
                    branch_lift_category="nested_or_method",
                    evidence_lift_status="refused",
                    evidence_lift_reason="function not at module top level (nested or method)",
                    evidence_lift_category="nested_or_method",
                )
            )
            continue

        b_status, b_reason, b_cat = _try_branch_lift(usable_source, site.function_name)
        e_status, e_reason, e_cat = _try_evidence_lift(usable_source, site.function_name)

        records.append(
            SiteRecord(
                corpus=corpus.name,
                file_path=site.file_path,
                function_name=site.function_name,
                pattern=site.pattern,
                line_start=site.line_start,
                fit_score=site.fit_score,
                label_cardinality=site.label_cardinality,
                regime=site.regime,
                lift_status=site.lift_status,
                hazards=[asdict(h) for h in site.hazards],
                branch_lift_status=b_status,
                branch_lift_reason=b_reason,
                branch_lift_category=b_cat,
                evidence_lift_status=e_status,
                evidence_lift_reason=e_reason,
                evidence_lift_category=e_cat,
            )
        )

    return records


# ---------------------------------------------------------------------------
# Aggregation + Markdown rendering
# ---------------------------------------------------------------------------


def _pct(part: int, total: int) -> str:
    if total == 0:
        return "0.0%"
    return f"{(100.0 * part / total):.1f}%"


def _status_breakdown(records: list[SiteRecord]) -> tuple[int, int, int, int]:
    total = len(records)
    auto = sum(1 for r in records if r.lift_status == LiftStatus.AUTO_LIFTABLE.value)
    needs = sum(1 for r in records if r.lift_status == LiftStatus.NEEDS_ANNOTATION.value)
    refused = sum(1 for r in records if r.lift_status == LiftStatus.REFUSED.value)
    return total, auto, needs, refused


def _refusal_histogram(records: list[SiteRecord]) -> Counter:
    """Count by refusal category across BOTH lifters' outputs.

    A site that's refused by both lifters with the same category counts
    once. A site that's refused by both lifters with different
    categories contributes to both bins.
    """
    cats: Counter = Counter()
    for r in records:
        seen: set[str] = set()
        if r.branch_lift_status == "refused" and r.branch_lift_category:
            seen.add(r.branch_lift_category)
        if r.evidence_lift_status == "refused" and r.evidence_lift_category:
            seen.add(r.evidence_lift_category)
        for cat in seen:
            cats[cat] += 1
    return cats


def _per_lifter_counts(records: list[SiteRecord]) -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {
        "branch": {"success": 0, "refused": 0, "error": 0},
        "evidence": {"success": 0, "refused": 0, "error": 0},
    }
    for r in records:
        out["branch"][r.branch_lift_status] = out["branch"].get(r.branch_lift_status, 0) + 1
        out["evidence"][r.evidence_lift_status] = out["evidence"].get(r.evidence_lift_status, 0) + 1
    return out


def _disagreement_count(records: list[SiteRecord]) -> dict[str, int]:
    """Where do the two lifters disagree?

    Returns counts for:
      - branch_only_success: branch succeeds, evidence refuses/errors
      - evidence_only_success: evidence succeeds, branch refuses/errors
      - both_success
      - both_refused
    """
    out = {
        "branch_only_success": 0,
        "evidence_only_success": 0,
        "both_success": 0,
        "both_refused": 0,
        "other": 0,
    }
    for r in records:
        b = r.branch_lift_status == "success"
        e = r.evidence_lift_status == "success"
        if b and e:
            out["both_success"] += 1
        elif b and not e:
            out["branch_only_success"] += 1
        elif e and not b:
            out["evidence_only_success"] += 1
        elif r.branch_lift_status == "refused" and r.evidence_lift_status == "refused":
            out["both_refused"] += 1
        else:
            out["other"] += 1
    return out


def render_markdown(records: list[SiteRecord], corpora: list[Corpus]) -> str:
    lines: list[str] = []
    lines.append("# Auto-lift sizing study (2026-04-27)")
    lines.append("")
    lines.append("Retroactive Phase 2-5 gate. Walks examples plus the cloned landing")
    lines.append("corpora, runs `analyze` then attempts both lifters per site.")
    lines.append("")

    # Corpus presence summary.
    lines.append("## Corpora scanned")
    lines.append("")
    lines.append("| Corpus | Present | Sites |")
    lines.append("|---|---|---:|")
    by_corpus: dict[str, list[SiteRecord]] = {}
    for r in records:
        by_corpus.setdefault(r.corpus, []).append(r)
    for c in corpora:
        n = len(by_corpus.get(c.name, []))
        lines.append(f"| {c.name} | {'yes' if c.present else 'MISSING'} | {n} |")
    lines.append("")

    # Overall headline.
    total, auto, needs, refused = _status_breakdown(records)
    lines.append("## Overall lift status (analyzer verdict)")
    lines.append("")
    lines.append(f"- Total candidate sites: **{total}**")
    lines.append(f"- auto_liftable: **{auto}** ({_pct(auto, total)})")
    lines.append(f"- needs_annotation: **{needs}** ({_pct(needs, total)})")
    lines.append(f"- refused: **{refused}** ({_pct(refused, total)})")
    lines.append("")

    # By corpus.
    lines.append("## By corpus")
    lines.append("")
    lines.append("| Corpus | Sites | auto | needs | refused |")
    lines.append("|---|---:|---:|---:|---:|")
    for c in corpora:
        rs = by_corpus.get(c.name, [])
        t, a, n, rf = _status_breakdown(rs)
        if t == 0 and not c.present:
            lines.append(f"| {c.name} | (missing) | . | . | . |")
            continue
        lines.append(
            f"| {c.name} | {t} | {a} ({_pct(a, t)}) | {n} ({_pct(n, t)}) | {rf} ({_pct(rf, t)}) |"
        )
    lines.append("")

    # Per-lifter outcomes.
    pl = _per_lifter_counts(records)
    lines.append("## Per-lifter outcomes")
    lines.append("")
    lines.append("| Lifter | success | refused | error |")
    lines.append("|---|---:|---:|---:|")
    for name in ("branch", "evidence"):
        d = pl[name]
        s, rf, er = d.get("success", 0), d.get("refused", 0), d.get("error", 0)
        lines.append(
            f"| {name} | {s} ({_pct(s, total)}) | "
            f"{rf} ({_pct(rf, total)}) | {er} ({_pct(er, total)}) |"
        )
    lines.append("")

    dis = _disagreement_count(records)
    lines.append("### Lifter agreement")
    lines.append("")
    lines.append(f"- both succeed: **{dis['both_success']}** ({_pct(dis['both_success'], total)})")
    lines.append(f"- both refuse: **{dis['both_refused']}** ({_pct(dis['both_refused'], total)})")
    bo = dis["branch_only_success"]
    eo = dis["evidence_only_success"]
    lines.append(f"- branch only succeeds: **{bo}** ({_pct(bo, total)})")
    lines.append(f"- evidence only succeeds: **{eo}** ({_pct(eo, total)})")
    lines.append(f"- mixed (one error, one not): **{dis['other']}** ({_pct(dis['other'], total)})")
    lines.append("")

    # Refusal histogram.
    hist = _refusal_histogram(records)
    lines.append("## Refusal histogram (any lifter)")
    lines.append("")
    lines.append("| Category | Count |")
    lines.append("|---|---:|")
    for cat, count in hist.most_common():
        lines.append(f"| {cat} | {count} |")
    lines.append("")

    # Top 20 refused sites by fit score.
    refused_sites = [
        r
        for r in records
        if r.branch_lift_status == "refused" or r.evidence_lift_status == "refused"
    ]
    refused_sites.sort(key=lambda r: r.fit_score, reverse=True)
    lines.append("## Top 20 refused sites by fit_score")
    lines.append("")
    lines.append(
        "| Corpus | File:Line | Function | Pattern | Fit | Branch | Evidence | First refusal |"
    )
    lines.append("|---|---|---|---|---:|---|---|---|")
    for r in refused_sites[:20]:
        first_reason = r.branch_lift_reason or r.evidence_lift_reason or ""
        # Trim long reasons; replace any em-dashes with hyphens (no em-dashes in the report).
        first_reason = first_reason.replace("—", " - ").replace("–", "-")
        if len(first_reason) > 80:
            first_reason = first_reason[:77] + "..."
        lines.append(
            f"| {r.corpus} | `{r.file_path}:{r.line_start}` | "
            f"`{r.function_name}` | {r.pattern} | {r.fit_score:.1f} | "
            f"{r.branch_lift_status} | {r.evidence_lift_status} | {first_reason} |"
        )
    lines.append("")

    # Notes.
    lines.append("## Notes")
    lines.append("")
    lines.append(
        "- Refusal histogram counts each (site, category) pair once per site, "
        "even if both lifters refused with that same category."
    )
    lines.append(
        "- `nested_or_method` is a sizing-study category, not an analyzer hazard. "
        "It marks sites whose function lives inside a class body or another def, "
        "which the v1 lifters skip by design (top-level only)."
    )
    lines.append(
        "- `internal_error` marks lifter exceptions other than `LiftRefused`. "
        "Any non-zero count here is a v1 bug to triage."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    corpora = discover_corpora()
    all_records: list[SiteRecord] = []
    for c in corpora:
        rs = study_corpus(c)
        all_records.extend(rs)

    # JSON output: full per-site dump plus aggregate stats.
    total, auto, needs, refused = _status_breakdown(all_records)
    pl = _per_lifter_counts(all_records)
    hist = _refusal_histogram(all_records)
    dis = _disagreement_count(all_records)
    payload = {
        "study_date": "2026-04-27",
        "corpora": [{"name": c.name, "root": str(c.root), "present": c.present} for c in corpora],
        "totals": {
            "total_sites": total,
            "auto_liftable": auto,
            "needs_annotation": needs,
            "refused": refused,
            "per_lifter": pl,
            "agreement": dis,
            "refusal_histogram": dict(hist),
        },
        "sites": [asdict(r) for r in all_records],
    }
    out_tmp = Path("/tmp/postrule-sizing-study.json")
    out_repo = _REPO_ROOT / "docs" / "working" / "sizing-study-2026-04-27.json"
    out_repo.parent.mkdir(parents=True, exist_ok=True)
    out_tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    out_repo.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md = render_markdown(all_records, corpora)
    print(md)
    print()
    print(f"JSON: {out_tmp}")
    print(f"JSON (working/): {out_repo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
