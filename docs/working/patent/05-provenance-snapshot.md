# Clean-IP Provenance Snapshot

**Purpose:** capture the state of the Dendra codebase + design
docs + commit history at the moment of the provisional filing so
the B-Tree Ventures provenance claim (per
`../patent-strategy.md` §7) is documented in a tamper-evident,
timestamped form. "First line of defense" if anyone ever
challenges provenance.

**When to run:** once, on Day 1 of the filing sequence (Step 1 of
`00-filing-checklist.md`). **Before** any significant code changes
for the filing.

---

## What the snapshot captures

A single compressed archive `provenance-<date>.tar.gz` containing:

| File in archive | Contents |
|---|---|
| `git-log-full.txt` | Full `git log --all --source --format=...` output for the Dendra repository. |
| `git-authors.txt` | `git shortlog --summary --email --all` — commit-count by author, demonstrating sole committership. |
| `filesystem-metadata.txt` | `ls -la` / `find` output for the repo tree with inode/mtime, showing personal-machine storage location. |
| `dendra-snapshot.tar.gz` | `git archive HEAD` — the reference implementation at priority-date commit. |
| `docs-snapshot.tar.gz` | `tar` of the `docs/` directory at priority date (paper, strategy, marketing). |
| `provisional-packet.tar.gz` | Copies of the filed patent documents (spec, cover sheet, drawings, declarations). |
| `pyproject-pinned.toml` | Copy of `pyproject.toml` at priority date — shows dependency set. |
| `sha256sums.txt` | SHA-256 hashes of every file above. |
| `README-provenance.md` | This file, plus the filing-date timestamp. |

Archive is stored:
- One copy on the filing machine.
- One copy in personal cloud backup.
- One copy on an off-machine encrypted drive.

---

## Provenance-capture script

Save this as `snapshot.sh` at the Dendra repo root. Run it once
with `bash snapshot.sh`.

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
cat > "${OUT_DIR}/README-provenance.md" <<EOF
# Dendra Provenance Snapshot — ${TODAY}

Captured for B-Tree Ventures LLC provisional patent application
filing.

Invention: System and Method for Graduated-Autonomy
Classification with Statistically-Gated Phase Transitions, and
Companion Analyzer System.

Inventor: Benjamin Booth (ben@b-treeventures.com).
Assignee: B-Tree Ventures, LLC.
Ownership: sole — no institutional or academic co-ownership.

Files in this archive:
  - git-log-full.txt: full commit history with author + timestamps
  - git-authors.txt: author summary showing sole committership
  - filesystem-metadata.txt: repo-tree file listing + mtimes
  - dendra-snapshot.tar.gz: reference implementation at HEAD
  - docs-snapshot.tar.gz: paper, strategy, marketing, patent
  - pyproject-pinned.toml: dependency manifest
  - sha256sums.txt: SHA-256 of every file here

Machine:       $(uname -a)
User:          $(whoami)
Working dir:   $(pwd)
Git SHA:       $(git rev-parse HEAD)
Git ref:       $(git symbolic-ref --short HEAD 2>/dev/null || echo detached)
Capture date:  $(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

echo "[8/8] Computing SHA-256 sums..."
(cd "${OUT_DIR}" && shasum -a 256 *.txt *.tar.gz *.toml *.md \
    > sha256sums.txt) 2>/dev/null || \
(cd "${OUT_DIR}" && sha256sum *.txt *.tar.gz *.toml *.md \
    > sha256sums.txt)

echo "[done] Bundling..."
tar -czf "${ARCHIVE}" -C "$(dirname "${OUT_DIR}")" \
    "$(basename "${OUT_DIR}")"

echo ""
echo "Archive:      ${ARCHIVE}"
echo "Size:         $(du -h "${ARCHIVE}" | cut -f1)"
echo "SHA-256:      $(shasum -a 256 "${ARCHIVE}" 2>/dev/null || sha256sum "${ARCHIVE}")"
echo ""
echo "Next steps:"
echo "  1. Copy ${ARCHIVE} to personal cloud backup."
echo "  2. Copy ${ARCHIVE} to off-machine encrypted drive."
echo "  3. Record the SHA-256 above in your filing notes."
echo "  4. Proceed to STEP 2 of 00-filing-checklist.md."
```

---

## After filing — add the USPTO receipt

Once the provisional is filed and USPTO Patent Center returns the
filing receipt (the PDF with Application Number + Priority Date),
re-run the script in an incremental mode:

```bash
# Add the USPTO receipt to the archive
tar -rf "provenance-${TODAY}.tar" \
    "USPTO-filing-receipt-$(date +%Y-%m-%d).pdf"
# Re-gzip and re-hash
```

Or simply create a second archive `post-filing-<date>.tar.gz`
containing the receipt + a SHA-256-referenced pointer back to the
pre-filing snapshot.

---

## Why this matters

Patent-law challenges to provenance can arise years after the
filing date. The snapshot makes it trivial to answer questions
like:

- "Was the invention in practice before the priority date?" —
  **Yes**: here is the git log with commit dates and the source
  tree at that time.
- "Who contributed?" — **Sole inventor**: here is the author
  summary.
- "Where was it developed?" — **Personal machine**: here is the
  filesystem metadata showing the path and timestamps.
- "Was there any institutional involvement?" — **No**: here is a
  clean dependency manifest and no references to any institutional
  codebase in the commit history.

Five minutes of work on filing day buys durable defensibility.

---

_Prepared 2026-04-20 for B-Tree Ventures LLC provisional filing._
