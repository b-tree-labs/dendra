# Copyright (c) 2026 B-Tree Labs
# SPDX-License-Identifier: Apache-2.0
#!/usr/bin/env bash
#
# Mirrors .github/workflows/dco.yml — verifies every commit since the
# merge-base with origin/main has a Signed-off-by trailer that matches
# its author email.

set -euo pipefail

# Refresh the remote ref so merge-base is accurate.
git fetch origin main --quiet 2>/dev/null || true

base=$(git merge-base HEAD origin/main)
head=$(git rev-parse HEAD)

if [[ "$base" == "$head" ]]; then
  echo "No commits ahead of origin/main — nothing to check."
  exit 0
fi

missing=0
checked=0

for sha in $(git rev-list "$base..$head"); do
  checked=$((checked + 1))
  author_email=$(git log -1 --format='%ae' "$sha")
  signoff=$(git log -1 --format='%B' "$sha" \
    | grep -E '^Signed-off-by: .+ <.+@.+>' || true)

  if [ -z "$signoff" ]; then
    echo "ERROR: $sha — missing Signed-off-by trailer ($(git log -1 --format='%s' "$sha"))"
    missing=$((missing + 1))
    continue
  fi

  if ! echo "$signoff" | grep -qF "<$author_email>"; then
    echo "ERROR: $sha — sign-off email does not match author ($author_email)"
    echo "       got: $signoff"
    missing=$((missing + 1))
  fi
done

echo "Checked $checked commit(s) ahead of origin/main."
if [ "$missing" -gt 0 ]; then
  echo "FAILED — $missing commit(s) missing or mis-attributed sign-off."
  echo "Fix with: git rebase --signoff $base"
  exit 1
fi
echo "PASSED — all commits carry a matching Signed-off-by trailer."
