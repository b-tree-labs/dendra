# Copyright (c) 2026 B-Tree Labs
# SPDX-License-Identifier: Apache-2.0
#!/usr/bin/env bash
#
# Mirrors .github/workflows/install-smoke.yml for the current interpreter.
# The remote runs a 6-cell matrix (mac+ubuntu × py3.10/3.12/3.13); locally
# we only run one cell, so platform-specific regressions can still slip
# through. That's the trade-off — local should be a fast sanity check, not
# a full matrix.
#
# Builds a wheel in a temp dir, installs into a fresh venv, runs the smoke
# imports and example gallery (01–05). Cleans up on exit.

set -euo pipefail

cd "$(dirname "$0")/../.."

tmp=$(mktemp -d -t postrule-smoke-XXXXXX)
trap 'rm -rf "$tmp"' EXIT

# We need a Python with `build` available to make the wheel. Modern macOS
# Homebrew Pythons are PEP-668 externally-managed, so we bootstrap a
# build-only venv first instead of touching system pip.
echo "Bootstrapping build venv in $tmp/build ..."
python3 -m venv "$tmp/build"
"$tmp/build/bin/pip" install --quiet --upgrade pip build

echo "Building wheel into $tmp/dist ..."
"$tmp/build/bin/python" -m build --outdir "$tmp/dist" >/dev/null

echo "Creating fresh smoke venv in $tmp/venv ..."
python3 -m venv "$tmp/venv"
# shellcheck source=/dev/null
source "$tmp/venv/bin/activate"

echo "Installing wheel ..."
pip install --quiet "$tmp"/dist/*.whl

echo "Smoke-test imports ..."
python -c "import postrule; print('postrule import: ok')"
python -c "from postrule import ml_switch, Phase, SwitchConfig, LearnedSwitch; print('client SDK imports: ok')"
postrule --help >/dev/null && echo "postrule --help: ok"

echo "Running example gallery (01-05) ..."
for example in examples/01_hello_world.py \
               examples/02_outcome_log.py \
               examples/03_safety_critical.py \
               examples/04_llm_shadow.py \
               examples/05_output_safety.py; do
  if [[ ! -f "$example" ]]; then
    echo "  ! $example missing — skipping"
    continue
  fi
  echo "  → $example"
  python "$example" >/dev/null
done

echo "PASSED — install + smoke-test + example gallery clean."
