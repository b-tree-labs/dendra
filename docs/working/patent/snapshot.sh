#!/usr/bin/env bash
# Dendra provisional-patent provenance snapshot.
# Run from the root of the Dendra git repository.
#
#     bash docs/working/patent/snapshot.sh
#
# Produces ./provenance-<YYYY-MM-DD>/ + ./provenance-<YYYY-MM-DD>.tar.gz
# containing the git log, source tree at HEAD, docs tree, pyproject,
# filesystem metadata, a provenance README, and SHA-256 sums.
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
{
    ls -la .
    echo "---"
    # macOS find lacks -printf; use stat for mtime + size fallback.
    find . -maxdepth 3 -type f \
        -not -path './.git/*' -not -path './.venv/*' \
        -not -path '*/__pycache__/*' -not -path '*/.pytest_cache/*' \
        -not -path './provenance-*' \
        -exec stat -f '%N %m %z' {} + 2>/dev/null || \
    find . -maxdepth 3 -type f \
        -not -path './.git/*' -not -path './.venv/*' \
        -not -path '*/__pycache__/*' -not -path '*/.pytest_cache/*' \
        -not -path './provenance-*'
} > "${OUT_DIR}/filesystem-metadata.txt"

echo "[4/8] Capturing source tree at HEAD..."
git archive --format=tar.gz HEAD > "${OUT_DIR}/dendra-snapshot.tar.gz"

echo "[5/8] Capturing docs tree..."
tar -czf "${OUT_DIR}/docs-snapshot.tar.gz" docs/

echo "[6/8] Copying pyproject..."
cp pyproject.toml "${OUT_DIR}/pyproject-pinned.toml"

echo "[7/8] Writing README..."
cat > "${OUT_DIR}/README-provenance.md" <<EOF
# Dendra Provenance Snapshot — ${TODAY}

Captured for B-Tree Ventures LLC provisional patent application filing.

Invention: System and Method for Graduated-Autonomy Classification with
Statistically-Gated Phase Transitions, and Companion Analyzer System.

Inventor:  Benjamin Booth (ben@b-treeventures.com).
Assignee:  B-Tree Ventures, LLC.
Ownership: sole — no institutional or academic co-ownership.

Files in this archive:
  - git-log-full.txt        full commit history with author + timestamps
  - git-authors.txt         author summary showing sole committership
  - filesystem-metadata.txt repo-tree file listing + mtimes
  - dendra-snapshot.tar.gz  reference implementation at HEAD
  - docs-snapshot.tar.gz    paper, strategy, marketing, patent
  - pyproject-pinned.toml   dependency manifest
  - sha256sums.txt          SHA-256 of every file here

Machine:       $(uname -a)
User:          $(whoami)
Working dir:   $(pwd)
Git SHA:       $(git rev-parse HEAD)
Git ref:       $(git symbolic-ref --short HEAD 2>/dev/null || echo detached)
Capture date:  $(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

echo "[8/8] Computing SHA-256 sums..."
(cd "${OUT_DIR}" && \
    { shasum -a 256 ./*.txt ./*.tar.gz ./*.toml ./*.md 2>/dev/null || \
      sha256sum  ./*.txt ./*.tar.gz ./*.toml ./*.md; } \
    > sha256sums.txt)

echo "[bundle] Creating archive..."
tar -czf "${ARCHIVE}" -C "$(dirname "${OUT_DIR}")" "$(basename "${OUT_DIR}")"

echo ""
echo "Archive:  ${ARCHIVE}"
echo "Size:     $(du -h "${ARCHIVE}" | cut -f1)"
echo "SHA-256:  $(shasum -a 256 "${ARCHIVE}" 2>/dev/null || sha256sum "${ARCHIVE}")"
echo ""
echo "Next steps:"
echo "  1. Copy ${ARCHIVE} to personal cloud backup."
echo "  2. Copy ${ARCHIVE} to off-machine encrypted drive."
echo "  3. Record the SHA-256 above in your filing notes."
