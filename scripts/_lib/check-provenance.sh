# Copyright (c) 2026 B-Tree Labs
# SPDX-License-Identifier: Apache-2.0
#!/usr/bin/env bash
#
# Mirrors the provenance-scan job in b-tree-labs/.github python-ci.yml@v1.
# The shared CI is configured (see .github/workflows/ci.yml) with:
#   provenance-forbidden-patterns: 'utexas|UT Austin|bbooth@'
#   provenance-paths: src/ tests/ docs/ examples/ landing/ README.md
#                     CHANGELOG.md SECURITY.md CONTRIBUTING.md CODEOWNERS
#                     LICENSE.md LICENSING.md LICENSE-APACHE LICENSE-BSL
#                     NOTICE TRADEMARKS.md SUPPORT.md pyproject.toml
# Keep these constants in sync with ci.yml.

set -euo pipefail

PATTERNS='utexas|UT Austin|bbooth@'
PATHS=(
  src tests docs examples landing
  README.md CHANGELOG.md SECURITY.md CONTRIBUTING.md CODEOWNERS
  LICENSE.md LICENSING.md LICENSE-APACHE LICENSE-BSL
  NOTICE TRADEMARKS.md SUPPORT.md pyproject.toml
)

# Restrict to existing paths (some are optional in early phases).
existing=()
for p in "${PATHS[@]}"; do
  [[ -e "$p" ]] && existing+=("$p")
done

if [[ ${#existing[@]} -eq 0 ]]; then
  echo "No provenance paths exist; nothing to scan."
  exit 0
fi

# `grep -r -E -I` to skip binary files. Suppress missing-file noise.
matches=$(grep -r -E -I "$PATTERNS" "${existing[@]}" 2>/dev/null || true)

if [[ -n "$matches" ]]; then
  echo "Forbidden provenance pattern matches found:"
  printf '%s\n' "$matches"
  echo ""
  echo "Patterns: $PATTERNS"
  echo "These should not appear in shipped artifacts."
  exit 1
fi

echo "PASSED — no forbidden provenance patterns found across ${#existing[@]} path(s)."
