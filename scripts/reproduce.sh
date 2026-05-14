#!/usr/bin/env bash
# Reproduce every measurement cited in the Postrule paper and the README.
#
# Runs from a fresh install:
#   1. pip install -e '.[dev,train,bench,viz]'
#   2. bash scripts/reproduce.sh
#
# Writes all artifacts under docs/papers/2026-when-should-a-rule-learn/
# results/reproduced-<YYYYMMDD>/ so nothing overwrites the committed
# reference data.

set -euo pipefail

TODAY=$(date +%Y-%m-%d)
RESULTS_DIR="docs/papers/2026-when-should-a-rule-learn/results/reproduced-${TODAY}"
mkdir -p "${RESULTS_DIR}"

export PYTHONHASHSEED=0

BENCHES=(atis hwu64 banking77 clinc150)

echo "==> §5 transition-curve measurements (4 benchmarks)"
for BENCH in "${BENCHES[@]}"; do
  OUT="${RESULTS_DIR}/${BENCH}.jsonl"
  echo "    [bench] ${BENCH} -> ${OUT}"
  python -m postrule.cli bench "${BENCH}" \
      --checkpoint-every 500 > "${OUT}"
done

echo ""
echo "==> §5.2 seed-size sensitivity (seed=1000 on each benchmark)"
for BENCH in "${BENCHES[@]}"; do
  OUT="${RESULTS_DIR}/${BENCH}_seed1000.jsonl"
  echo "    [bench] ${BENCH} seed-size=1000 -> ${OUT}"
  python -m postrule.cli bench "${BENCH}" \
      --seed-size 1000 \
      --checkpoint-every 1000 > "${OUT}"
done

echo ""
echo "==> §5.1 Figure 1 (four-panel transition curves)"
python -m postrule.cli plot \
    "${RESULTS_DIR}/atis.jsonl" \
    "${RESULTS_DIR}/hwu64.jsonl" \
    "${RESULTS_DIR}/banking77.jsonl" \
    "${RESULTS_DIR}/clinc150.jsonl" \
    -o "${RESULTS_DIR}/figure-1-transition-curves.png" \
    --title "Figure 1: Rule-to-ML transition curves (reproduced ${TODAY})"

echo ""
echo "==> §8 latency measurements"
python -m pytest tests/test_latency.py -v -s \
    2>&1 | tee "${RESULTS_DIR}/latency-measurements.txt"

echo ""
echo "==> §8.3 security benchmarks"
python -m pytest tests/test_security_benchmarks.py -v -s \
    2>&1 | tee "${RESULTS_DIR}/security-benchmarks.txt"

echo ""
echo "==> §8 output-safety demonstration"
python -m pytest tests/test_output_safety.py -v \
    2>&1 | tee "${RESULTS_DIR}/output-safety.txt"

echo ""
echo "==> environment record (for provenance)"
python --version         > "${RESULTS_DIR}/env-python.txt"
pip freeze              > "${RESULTS_DIR}/env-pip-freeze.txt"
git log -1 --pretty=full > "${RESULTS_DIR}/env-git-head.txt"
date -u +%Y-%m-%dT%H:%M:%SZ > "${RESULTS_DIR}/env-timestamp.txt"

echo ""
echo "==> done -- all results in ${RESULTS_DIR}"
