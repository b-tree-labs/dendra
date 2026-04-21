```bash
#!/usr/bin/env bash
# Dendra provisional-patent provenance snapshot
# Run from the root of the Dendra git repository.
set -euo pipefail

TODAY=$(date +%Y-%m-%d)
OUT_DIR="./provenance-${TODAY}"
ARCHIVE="./provenance-${TODAY}.tar.gz"

mkdir -p "${OUT_DIR}"

echo "[1/8] Capturing full git log..."
git log --all --source --format="%h %aI %ae <%an> %s" \
    > "${OUT_DIR}/git-log-full.txt"

echo "[2/8] Capturing author summary..."
git shortlog --summary --email --all > "${OUT_DIR}/git-authors.txt"

echo "[3/8] Capturing filesystem metadata..."
(ls -la . && echo "---" && find . -maxdepth 3 -type f \
    -not -path './.git/*' -not -path './.venv/*' \
    -not -path '*/__pycache__/*' -not -path '*/.pytest_cache/*' \
    -printf '%p %T@ %s\n' 2>/dev/null || \
    find . -maxdepth 3 -type f \
    -not -path './.git/*' -not -path './.venv/*' \
    -not -path '*/__pycache__/*' -not -path '*/.pytest_cache/*') \
    > "${OUT_DIR}/filesystem-metadata.txt"

echo "[4/8] Capturing source tree at HEAD..."
git archive --format=tar.gz HEAD \
    > "${OUT_DIR}/dendra-snapshot.tar.gz"

echo "[5/8] Capturing docs tree..."
tar -czf "${OUT_DIR}/docs-snapshot.tar.gz" docs/

echo "[6/8] Copying pyproject..."
cp pyproject.toml "${OUT_DIR}/pyproject-pinned.toml"

echo "[7/8] Writing README..."
cat > "${OUT_DIR}/README-provenance.md"