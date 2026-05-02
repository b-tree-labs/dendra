#!/usr/bin/env bash
# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0
#
# Mirrors .github/workflows/license-check.yml. The BSL allowlist must
# match the workflow exactly — if you edit one, edit the other.
# (TODO: lift the workflow's bash to call this script directly.)

set -euo pipefail

is_bsl_allowed() {
  case "$1" in
    src/dendra/analyzer.py|\
    src/dendra/auth.py|\
    src/dendra/benchmarks/harness.py|\
    src/dendra/cli.py|\
    src/dendra/cloud/__init__.py|\
    src/dendra/cloud/registry.py|\
    src/dendra/cloud/sync.py|\
    src/dendra/cloud/team_corpus.py|\
    src/dendra/cloud/report/__init__.py|\
    src/dendra/cloud/report/aggregator.py|\
    src/dendra/cloud/report/charts.py|\
    src/dendra/cloud/report/discovery.py|\
    src/dendra/cloud/report/hypotheses.py|\
    src/dendra/cloud/report/render_markdown.py|\
    src/dendra/cloud/report/summary.py|\
    src/dendra/lifters/__init__.py|\
    src/dendra/lifters/branch.py|\
    src/dendra/lifters/evidence.py|\
    src/dendra/mcp_server.py|\
    src/dendra/research.py|\
    src/dendra/roi.py|\
    cloud/aggregator/run.py|\
    landing/wasm/dendra_analyzer.py|\
    scripts/sizing_study.py|\
    tests/test_analyzer.py|\
    tests/test_auth.py|\
    tests/test_benchmarks.py|\
    tests/test_cli.py|\
    tests/test_cloud_report.py|\
    tests/test_cloud_sync.py|\
    tests/test_enrich_landing_corpus.py|\
    tests/test_lifter_branch.py|\
    tests/test_lifter_branch_v1_5.py|\
    tests/test_lifter_evidence.py|\
    tests/test_lifter_evidence_v1_1.py|\
    tests/test_mcp_server.py|\
    tests/test_research.py|\
    tests/test_roi.py)
      return 0 ;;
    *)
      return 1 ;;
  esac
}

errors=0
checked=0

while IFS= read -r file; do
  checked=$((checked + 1))

  spdx_line=$(head -5 "$file" \
    | grep -nE 'SPDX-License-Identifier:' \
    | head -1 \
    || true)

  if [ -z "$spdx_line" ]; then
    echo "ERROR: $file:1 — missing SPDX-License-Identifier header in the first 5 lines"
    errors=$((errors + 1))
    continue
  fi

  spdx_value=$(printf '%s' "$spdx_line" \
    | sed -nE 's/.*SPDX-License-Identifier:[[:space:]]*([A-Za-z0-9._+-]+).*/\1/p')

  case "$spdx_value" in
    "Apache-2.0")
      :
      ;;
    "LicenseRef-BSL-1.1")
      if ! is_bsl_allowed "$file"; then
        echo "ERROR: $file — carries BSL SPDX but is not on the BSL path allowlist (edit .github/workflows/license-check.yml AND scripts/_lib/check-license-headers.sh)"
        errors=$((errors + 1))
      fi
      ;;
    "")
      echo "ERROR: $file — empty or unparseable SPDX-License-Identifier"
      errors=$((errors + 1))
      ;;
    *)
      echo "ERROR: $file — unknown SPDX '$spdx_value'; only 'Apache-2.0' and 'LicenseRef-BSL-1.1' allowed"
      errors=$((errors + 1))
      ;;
  esac
done < <(git ls-files '*.py')

echo "Checked $checked Python files."
if [ "$errors" -gt 0 ]; then
  echo "FAILED with $errors error(s)."
  exit 1
fi
echo "PASSED — all SPDX headers valid + BSL allowlist clean."
