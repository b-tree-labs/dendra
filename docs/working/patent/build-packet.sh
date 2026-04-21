#!/usr/bin/env bash
# Build the Dendra provisional-patent filing packet.
#
#     bash docs/working/patent/build-packet.sh
#
# Does, in order:
#   1. Normalize any line-split hyphenated compounds in source .md files.
#   2. Re-extract the 8 Mermaid figure sources from 04-drawings.md.
#   3. Render each figure; wrap with a FIG.N label + description via a
#      tectonic LaTeX wrapper. Uniform target scale 0.45 gives every
#      figure the same apparent text size; figures that would exceed
#      the page at 0.45 are scaled to page-maximum instead.
#   4. Render cover sheet, micro-entity declaration, specification.
#   5. Concatenate into docs/working/patent/dendra-ppa.pdf.
set -euo pipefail
cd "$(dirname "$0")"

PY=/Users/ben/Projects/UT_Computational_NE/.venv/bin/python

echo "[1/5] Normalizing split hyphenated compounds..."
"$PY" <<'PYFIX'
import re, pathlib
pat = re.compile(r"([A-Za-z])-\n[ \t]*([A-Za-z][A-Za-z-]*)", re.MULTILINE)
total = 0
for name in ["01-provisional-specification.md","02-cover-sheet-SB16.md",
             "03-micro-entity-SB15A.md","personal-invention-declaration.md",
             "04-drawings.md"]:
    p = pathlib.Path(name)
    if not p.exists(): continue
    text = p.read_text()
    n = 0
    while True:
        text2, k = pat.subn(r"\1-\2", text)
        if k == 0: break
        text, n = text2, n + k
    if n: p.write_text(text)
    total += n
print(f"  fixed {total} split compound(s)")
PYFIX

echo "[2/5] Re-extracting Mermaid sources..."
mkdir -p drawings
"$PY" <<'PYEXT'
import re, pathlib
src = pathlib.Path("04-drawings.md").read_text()
fig_re = re.compile(
    r"## FIG\.\s*(\d+)\s*[—\-]\s*([^\n]+)\n+"
    r"\*\*Description:\*\*\s*(.+?)\n+"
    r"```mermaid\n(.*?)\n```",
    re.DOTALL,
)
for m in fig_re.finditer(src):
    num = int(m.group(1))
    pathlib.Path(f"drawings/fig-{num:02d}.mmd").write_text(m.group(4).strip() + "\n")
PYEXT

echo "[3/5] Rendering figures with uniform text scale..."
cd drawings
for i in 01 02 03 04 05 06 07 08; do
  npx --yes @mermaid-js/mermaid-cli -i "fig-${i}.mmd" -o "fig-${i}-raw.pdf" \
      --configFile mermaid-config.json --backgroundColor white --pdfFit \
      >/dev/null 2>&1
done
cd ..

"$PY" <<'PYWRAP'
import re, pathlib, subprocess
from pypdf import PdfReader

# Consistency policy: a uniform apparent text size across all figures
# means a uniform scale factor from mermaid-native to PDF-page.
# Mermaid renders at 22px; at scale 0.45 that's ~10pt on the page,
# which is comfortably readable without dominating. Figures that
# would exceed a page at 0.45 are clamped to page-maximum.
TARGET_SCALE = 0.45
# With 0.5in margins on Letter: textwidth 7.5", textheight 10".
# Reserve space for title (~0.4") + caption (~0.6") + gaps.
MAX_W_IN = 7.5
MAX_H_IN = 8.7

src_md = pathlib.Path("04-drawings.md").read_text()
fig_re = re.compile(
    r"## FIG\.\s*(\d+)\s*[—\-]\s*([^\n]+)\n+"
    r"\*\*Description:\*\*\s*(.+?)\n+"
    r"```mermaid\n(.*?)\n```",
    re.DOTALL,
)

def latex_escape(s):
    for a, b in [("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"),
                 ("$", r"\$"), ("#", r"\#"), ("_", r"\_"), ("{", r"\{"),
                 ("}", r"\}"), ("~", r"\textasciitilde{}"),
                 ("^", r"\textasciicircum{}"), ("<", r"\textless{}"),
                 (">", r"\textgreater{}")]:
        s = s.replace(a, b)
    return re.sub(r" +", " ", s).strip()

TEMPLATE = r"""\documentclass[11pt,letterpaper]{article}
\usepackage[margin=0.5in]{geometry}
\usepackage{graphicx}
\usepackage{helvet}
\renewcommand{\familydefault}{\sfdefault}
\pagestyle{empty}
\begin{document}
\null\vfill
\begin{center}
{\Large\textbf{FIG. %(num)d --- %(title)s}}\\[1em]
\includegraphics[width=%(width_in).3fin]{fig-%(num02)s-raw.pdf}\\[1em]
\begin{minipage}{0.9\textwidth}
\footnotesize\raggedright %(description)s
\end{minipage}
\end{center}
\vfill
\end{document}
"""

for m in fig_re.finditer(src_md):
    num = int(m.group(1))
    title = m.group(2).strip()
    description = re.sub(r"\s+", " ", m.group(3).strip())
    raw = PdfReader(f"drawings/fig-{num:02d}-raw.pdf").pages[0]
    native_w_in = float(raw.mediabox.width) / 72
    native_h_in = float(raw.mediabox.height) / 72
    # Clamp scale so image fits within MAX_W / MAX_H.
    scale = min(TARGET_SCALE, MAX_W_IN / native_w_in, MAX_H_IN / native_h_in)
    width_in = native_w_in * scale
    height_in = native_h_in * scale
    tex = TEMPLATE % {
        "num": num, "num02": f"{num:02d}",
        "title": latex_escape(title),
        "description": latex_escape(description),
        "width_in": width_in,
    }
    pathlib.Path(f"drawings/fig-{num:02d}.tex").write_text(tex)
    r = subprocess.run(["tectonic", f"fig-{num:02d}.tex"],
                       capture_output=True, text=True, cwd="drawings")
    if r.returncode != 0:
        raise SystemExit(f"FIG {num} tectonic failed: {r.stderr[-400:]}")
    print(f"  FIG {num}: native {native_w_in:.2f}x{native_h_in:.2f}\"  "
          f"-> scale {scale:.3f}  -> {width_in:.2f}x{height_in:.2f}\"")
PYWRAP

echo "[4/5] Rendering cover sheet, micro-entity, specification..."
mkdir -p packet
for pair in "02-cover-sheet-SB16.md:02-cover-sheet.pdf" \
            "03-micro-entity-SB15A.md:03-micro-entity.pdf" \
            "01-provisional-specification.md:01-specification.pdf"; do
  src="${pair%:*}"
  out="${pair#*:}"
  pandoc "$src" -o "packet/$out" --pdf-engine=tectonic \
      -V geometry:margin=1in -V fontsize=11pt -V mainfont="Helvetica" \
      --include-in-header=header-tex-tweaks.tex >/dev/null 2>&1
done

echo "[5/5] Concatenating packet..."
pdfunite packet/02-cover-sheet.pdf packet/03-micro-entity.pdf \
    packet/01-specification.pdf \
    drawings/fig-01.pdf drawings/fig-02.pdf drawings/fig-03.pdf \
    drawings/fig-04.pdf drawings/fig-05.pdf drawings/fig-06.pdf \
    drawings/fig-07.pdf drawings/fig-08.pdf \
    dendra-ppa.pdf

PAGES=$("$PY" -c "from pypdf import PdfReader; print(len(PdfReader('dendra-ppa.pdf').pages))")
SIZE=$(du -h dendra-ppa.pdf | cut -f1)
echo ""
echo "  dendra-ppa.pdf: $PAGES pages, $SIZE"
