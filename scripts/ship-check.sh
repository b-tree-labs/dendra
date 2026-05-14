#!/usr/bin/env bash
# Copyright (c) 2026 B-Tree Labs
# SPDX-License-Identifier: Apache-2.0
#
# ship-check — local mirror of every GitHub Actions workflow that runs on
# push or pull_request to main. Refuses to declare green unless every
# workflow under .github/workflows/ either has a local mirror that ran,
# or is on the explicit waiver list below.
#
# Modes:
#   scripts/ship-check.sh                  # pre-push: run every local mirror
#   scripts/ship-check.sh --post-merge SHA # post-merge: poll gh for main runs
#   scripts/ship-check.sh --fast           # skip slow checks (install-smoke)
#   scripts/ship-check.sh --only NAMES     # comma-list of mirrors to run
#
# Contract: when ship-check exits 0, we expect main to stay green after
# merge. When main goes red anyway, ship-check is the bug — fix it, don't
# work around it.
#
# Adding a workflow:
#   1. Drop the .yml in .github/workflows/.
#   2. Either add a mirror function below + register it in MIRRORS, or
#      add the workflow name to WAIVERS with a reason.
#   3. ship-check will fail until you do one of those — by design.

set -euo pipefail

cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"

# Auto-activate the project venv if present and not already active.
# CI runs in a fresh venv created by setup-python; locally we prefer the
# repo's .venv so ship-check doesn't depend on the user remembering.
if [[ -z "${VIRTUAL_ENV:-}" && -f "$REPO_ROOT/.venv/bin/activate" ]]; then
  # shellcheck source=/dev/null
  source "$REPO_ROOT/.venv/bin/activate"
fi

# ─── waiver list ───────────────────────────────────────────────────────────
# Workflows we deliberately don't mirror locally. Each entry: name -> reason.
# Anything in here should also have a tracking issue or a structural reason
# that explains why a local run isn't possible/useful.
declare -A WAIVERS=(
  [release.yml]="tag-only — fires on 'git push --tags', not branch pushes"
  [security.yml]="upstream reusable broken (grype DB / gitleaks org-license / REUSE split-license); quarantined to schedule-only"
  [aggregator.yml]="cron-only (03:00 UTC nightly) — runs against staging/production D1 + commits to main; not locally mirrorable"
  [deploy-staging.yml]="deploys to Cloudflare staging on push:main; smoke tests live at tests/smoke/, but the deploy step itself runs against real Cloudflare infra"
  [deploy-production.yml]="tag-only (release-* tags); same Cloudflare-infra rationale as deploy-staging"
  [refresh-llm-prices.yml]="cron-only (Mondays 14:00 UTC) + workflow_dispatch; opens a PR if upstream LiteLLM JSON diffs"
)

# ─── mirror registry ───────────────────────────────────────────────────────
# Each workflow that runs on push:main or pull_request:main maps to a local
# mirror function defined below. The coverage check fails if a workflow is
# missing from both MIRRORS and WAIVERS.
declare -A MIRRORS=(
  [ci.yml]="mirror_ci"
  [coverage-ratchet.yml]="mirror_coverage_ratchet"
  [dco.yml]="mirror_dco"
  [install-smoke.yml]="mirror_install_smoke"
  [license-check.yml]="mirror_license_check"
)

# ─── output helpers ────────────────────────────────────────────────────────
RED=$'\033[31m'
GREEN=$'\033[32m'
YELLOW=$'\033[33m'
BOLD=$'\033[1m'
RESET=$'\033[0m'

step()    { printf "%s[%s]%s %s\n" "$BOLD" "$1" "$RESET" "$2"; }
ok()      { printf "  %s✓%s %s\n" "$GREEN" "$RESET" "$1"; }
fail()    { printf "  %s✗%s %s\n" "$RED" "$RESET" "$1"; }
info()    { printf "  %s•%s %s\n" "$YELLOW" "$RESET" "$1"; }

# ─── coverage check ────────────────────────────────────────────────────────
# Fails if a workflow file exists but isn't in MIRRORS or WAIVERS, or
# vice-versa (stale entry pointing at a deleted workflow).
coverage_check() {
  local wfdir="$REPO_ROOT/.github/workflows"
  local missing=0 stale=0

  for f in "$wfdir"/*.yml; do
    local name
    name="$(basename "$f")"
    if [[ -z "${MIRRORS[$name]:-}" && -z "${WAIVERS[$name]:-}" ]]; then
      fail "workflow '$name' has no local mirror and no waiver"
      fail "  → add a mirror function in scripts/ship-check.sh, or"
      fail "  → add an entry to WAIVERS with a reason"
      missing=$((missing + 1))
    fi
  done

  for name in "${!MIRRORS[@]}" "${!WAIVERS[@]}"; do
    if [[ ! -f "$wfdir/$name" ]]; then
      fail "stale entry: '$name' in ship-check.sh but no workflow file at $wfdir/$name"
      stale=$((stale + 1))
    fi
  done

  if (( missing > 0 || stale > 0 )); then
    return 1
  fi
}

# ─── individual mirrors ────────────────────────────────────────────────────

# Mirrors ci.yml → b-tree-labs/.github python-ci.yml@v1
# Jobs: Lint, Pre-commit, Provenance scan, Test (py3.10–3.13)
mirror_ci() {
  step "ci.yml" "ruff + pre-commit + pytest + provenance"

  if ! ruff check . >/tmp/ship-check-ruff.log 2>&1; then
    fail "ruff check"
    cat /tmp/ship-check-ruff.log
    return 1
  fi
  ok "ruff check"

  if ! ruff format --check . >/tmp/ship-check-rufffmt.log 2>&1; then
    fail "ruff format --check"
    cat /tmp/ship-check-rufffmt.log
    return 1
  fi
  ok "ruff format --check"

  if ! pre-commit run --all-files >/tmp/ship-check-precommit.log 2>&1; then
    fail "pre-commit"
    tail -30 /tmp/ship-check-precommit.log
    return 1
  fi
  ok "pre-commit"

  if ! pytest >/tmp/ship-check-pytest.log 2>&1; then
    fail "pytest"
    tail -30 /tmp/ship-check-pytest.log
    return 1
  fi
  ok "pytest ($(grep -E '[0-9]+ passed' /tmp/ship-check-pytest.log | tail -1))"

  if ! bash "$REPO_ROOT/scripts/_lib/check-provenance.sh" >/tmp/ship-check-prov.log 2>&1; then
    fail "provenance scan"
    cat /tmp/ship-check-prov.log
    return 1
  fi
  ok "provenance scan"
}

# Mirrors dco.yml — every commit since merge-base with origin/main must
# carry a Signed-off-by trailer that matches its author email.
mirror_dco() {
  step "dco.yml" "Signed-off-by on every commit since main"
  if ! bash "$REPO_ROOT/scripts/_lib/check-dco.sh" >/tmp/ship-check-dco.log 2>&1; then
    fail "DCO check"
    cat /tmp/ship-check-dco.log
    return 1
  fi
  ok "DCO ($(grep -c '^' /tmp/ship-check-dco.log) lines logged)"
}

# Mirrors install-smoke.yml. The remote runs a 6-cell matrix
# (mac+ubuntu × py3.10/3.12/3.13); locally we run one cell against the
# current interpreter. Slow (~60s); skipped under --fast.
mirror_install_smoke() {
  step "install-smoke.yml" "build wheel + install + import (current interpreter only)"

  if [[ "${SHIP_CHECK_FAST:-0}" == "1" ]]; then
    info "skipped under --fast"
    return 0
  fi

  if ! bash "$REPO_ROOT/scripts/_lib/install-smoke.sh" >/tmp/ship-check-smoke.log 2>&1; then
    fail "install-smoke"
    tail -30 /tmp/ship-check-smoke.log
    return 1
  fi
  ok "install-smoke"
}

# Mirrors coverage-ratchet.yml — pytest --cov + scripts/coverage_ratchet.py.
# Enforces R1 (no per-file regression), R2 (+5pp buffer for files with floor
# < 70%), and R3 (new files must enter at >= 60%).
mirror_coverage_ratchet() {
  step "coverage-ratchet.yml" "pytest --cov + per-file floor check"

  if ! pytest --cov=src/postrule --cov-report=json:coverage.json -q \
       >/tmp/ship-check-cov.log 2>&1; then
    fail "pytest --cov"
    tail -30 /tmp/ship-check-cov.log
    return 1
  fi
  ok "pytest --cov ($(grep -E '[0-9]+ passed' /tmp/ship-check-cov.log | tail -1))"

  if ! python "$REPO_ROOT/scripts/coverage_ratchet.py" \
       >/tmp/ship-check-ratchet.log 2>&1; then
    fail "coverage ratchet"
    cat /tmp/ship-check-ratchet.log
    return 1
  fi
  ok "coverage ratchet ($(tail -1 /tmp/ship-check-ratchet.log))"

  if ! python "$REPO_ROOT/scripts/check_integration_manifest.py" \
       >/tmp/ship-check-manifest.log 2>&1; then
    fail "integration manifest"
    cat /tmp/ship-check-manifest.log
    return 1
  fi
  ok "integration manifest ($(tail -1 /tmp/ship-check-manifest.log))"
}

# Mirrors license-check.yml — SPDX header + BSL path allowlist.
mirror_license_check() {
  step "license-check.yml" "SPDX headers + BSL path allowlist"
  if ! bash "$REPO_ROOT/scripts/_lib/check-license-headers.sh" >/tmp/ship-check-license.log 2>&1; then
    fail "license-check"
    cat /tmp/ship-check-license.log
    return 1
  fi
  ok "license-check"
}

# ─── post-merge poll ───────────────────────────────────────────────────────
# Asks gh for every run that fired on main for the given commit SHA, and
# fails loudly if anything's red. This is the safety net that would have
# caught the security.yml problem on day one.
post_merge() {
  local sha_input="$1"

  # Resolve short SHA / ref to full SHA so gh's --commit filter matches.
  local sha
  if ! sha=$(git rev-parse "$sha_input" 2>/dev/null); then
    fail "could not resolve '$sha_input' to a SHA (git rev-parse failed)"
    return 1
  fi
  step "post-merge" "polling main runs for $sha"

  # Pull all recent main runs and filter client-side so SHA-prefix arguments
  # work. (gh's `--commit` filter requires an exact match.)
  local rows
  rows=$(gh run list --branch main --limit 50 \
    --json name,conclusion,status,databaseId,headSha \
    --jq ".[] | select(.headSha == \"$sha\") | [.name, .status, .conclusion, .databaseId] | @tsv")

  if [[ -z "$rows" ]]; then
    info "no runs reported for $sha yet — try again in a minute"
    return 0
  fi

  local pending=0 failed=0 passed=0
  while IFS=$'\t' read -r name status conclusion id; do
    [[ -z "$name" ]] && continue
    case "$conclusion" in
      success)        ok    "$name"; passed=$((passed + 1)) ;;
      failure|cancelled|timed_out)
                      fail  "$name (run $id)"; failed=$((failed + 1)) ;;
      "")             info  "$name (status: $status)"; pending=$((pending + 1)) ;;
      *)              info  "$name (conclusion: $conclusion)" ;;
    esac
  done <<< "$rows"

  printf "\n"
  printf "  passed=%d  failed=%d  pending=%d\n" "$passed" "$failed" "$pending"
  if (( failed > 0 )); then
    fail "post-merge red. Inspect with: gh run view <run-id> --log-failed"
    return 1
  fi
  if (( pending > 0 )); then
    info "some runs still pending — re-run when they finish"
    return 0
  fi
  ok "post-merge green for $sha"
}

# ─── main ──────────────────────────────────────────────────────────────────
main() {
  local mode="pre-push"
  local sha=""
  local only=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --post-merge) mode="post-merge"; sha="$2"; shift 2 ;;
      --fast) export SHIP_CHECK_FAST=1; shift ;;
      --only) only="$2"; shift 2 ;;
      -h|--help)
        sed -n '3,25p' "$0"
        exit 0
        ;;
      *) fail "unknown arg: $1"; exit 2 ;;
    esac
  done

  if [[ "$mode" == "post-merge" ]]; then
    post_merge "$sha"
    exit $?
  fi

  printf "%s=== ship-check ===%s\n\n" "$BOLD" "$RESET"

  step "coverage" "every workflow has a mirror or waiver"
  if ! coverage_check; then
    exit 1
  fi
  ok "coverage check"
  printf "\n"

  local failed=0
  for name in "${!MIRRORS[@]}"; do
    if [[ -n "$only" ]] && ! [[ ",$only," == *",${MIRRORS[$name]#mirror_},"* ]]; then
      continue
    fi
    if ! "${MIRRORS[$name]}"; then
      failed=$((failed + 1))
    fi
    printf "\n"
  done

  printf "%s──────────────────────────────────────────%s\n" "$BOLD" "$RESET"
  if (( failed > 0 )); then
    printf "%s✗ ship-check red — %d mirror(s) failed.%s\n" "$RED" "$failed" "$RESET"
    exit 1
  fi

  printf "%s✓ ship-check green.%s\n" "$GREEN" "$RESET"
  printf "  Waived: "
  local first=1
  for name in "${!WAIVERS[@]}"; do
    [[ $first -eq 1 ]] || printf ", "
    printf "%s" "$name"
    first=0
  done
  printf "\n"
  printf "  After merge, run: scripts/ship-check.sh --post-merge \$(git rev-parse origin/main)\n"
}

main "$@"
