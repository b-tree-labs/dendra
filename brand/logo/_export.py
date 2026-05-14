# Copyright (c) 2026 B-Tree Labs
# SPDX-License-Identifier: Apache-2.0
"""Regenerate Postrule brand-kit PNG exports from the canonical SVGs.

Run: `python brand/logo/_export.py`. Requires `cairosvg` (`pip install
cairosvg`). Writes PNGs next to the source SVGs using the
``<stem>-<size>.png`` naming convention that matches the B-Tree Labs
brand-kit convention.

Favicon + mark sizes deliberately match what the landing page, README,
PyPI page, and social-card embeds need — additional sizes can be
added to the dictionary below without touching the rendering logic.
"""

from __future__ import annotations

from pathlib import Path

import cairosvg

HERE = Path(__file__).parent

# (svg_stem, [output_size_px ...])
# None for output_size means "render at natural dimensions" (used for
# wordmarks + social card, where the canvas ratio is load-bearing).
EXPORTS: dict[str, list[int | None]] = {
    "postrule-favicon": [16, 32, 180, 512],
    "postrule-mark": [1024],
    "postrule-mark-dark": [1024],
    "postrule-mark-mono-light": [1024],
    "postrule-mark-mono-dark": [1024],
    # Parent + sub-brand wordmarks. The canvas dimensions are
    # auto-computed by `_generate_wordmarks.py` to give symmetric
    # 50px L/R margins per word, so widths vary per sub-brand.
    # Each ships in three variants (light / -dark / -transparent)
    # × two layouts (horizontal / stacked).
    "postrule-wordmark-horizontal": [None],
    "postrule-wordmark-horizontal-dark": [None],
    "postrule-wordmark-horizontal-transparent": [None],
    "postrule-wordmark-stacked": [None],
    "postrule-wordmark-stacked-dark": [None],
    "postrule-wordmark-stacked-transparent": [None],
    # Sub-brand lockups — analyze
    "postrule-analyze-wordmark": [None],
    "postrule-analyze-wordmark-dark": [None],
    "postrule-analyze-wordmark-transparent": [None],
    "postrule-analyze-wordmark-stacked": [None],
    "postrule-analyze-wordmark-stacked-dark": [None],
    "postrule-analyze-wordmark-stacked-transparent": [None],
    # Sub-brand lockups — cloud
    "postrule-cloud-wordmark": [None],
    "postrule-cloud-wordmark-dark": [None],
    "postrule-cloud-wordmark-transparent": [None],
    "postrule-cloud-wordmark-stacked": [None],
    "postrule-cloud-wordmark-stacked-dark": [None],
    "postrule-cloud-wordmark-stacked-transparent": [None],
    # Sub-brand lockups — insight
    "postrule-insight-wordmark": [None],
    "postrule-insight-wordmark-dark": [None],
    "postrule-insight-wordmark-transparent": [None],
    "postrule-insight-wordmark-stacked": [None],
    "postrule-insight-wordmark-stacked-dark": [None],
    "postrule-insight-wordmark-stacked-transparent": [None],
    # Sub-brand lockups — research
    "postrule-research-wordmark": [None],
    "postrule-research-wordmark-dark": [None],
    "postrule-research-wordmark-transparent": [None],
    "postrule-research-wordmark-stacked": [None],
    "postrule-research-wordmark-stacked-dark": [None],
    "postrule-research-wordmark-stacked-transparent": [None],
    # Social card
    "postrule-social-card": [None],
    "postrule-social-card-dark": [None],
    # Applied assets — social banners + share previews
    "postrule-github-social-preview": [None],  # 1280×640 native
    "postrule-twitter-banner": [None],  # 1500×500 native
    "postrule-linkedin-banner": [None],  # 1128×191 native
}


def render(stem: str, size: int | None) -> Path:
    svg_path = HERE / f"{stem}.svg"
    if not svg_path.is_file():
        raise FileNotFoundError(svg_path)

    if size is None:
        # Native dimensions — cairosvg reads the viewBox.
        out_path = HERE / f"{stem}.png"
        cairosvg.svg2png(url=str(svg_path), write_to=str(out_path))
    else:
        out_path = HERE / f"{stem}-{size}.png"
        cairosvg.svg2png(
            url=str(svg_path),
            write_to=str(out_path),
            output_width=size,
            output_height=size,
        )
    return out_path


def main() -> None:
    for stem, sizes in EXPORTS.items():
        for size in sizes:
            out = render(stem, size)
            print(f"  {out.relative_to(HERE.parent.parent)}")


if __name__ == "__main__":
    main()
