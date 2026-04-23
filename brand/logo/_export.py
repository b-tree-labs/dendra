# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0
"""Regenerate Dendra brand-kit PNG exports from the canonical SVGs.

Run: `python brand/logo/_export.py`. Requires `cairosvg` (`pip install
cairosvg`). Writes PNGs next to the source SVGs using the
``<stem>-<size>.png`` naming convention that matches the Axiom Labs
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
    "dendra-favicon": [16, 32, 180, 512],
    "dendra-mark": [1024],
    "dendra-mark-dark": [1024],
    "dendra-mark-mono-light": [1024],
    "dendra-mark-mono-dark": [1024],
    "dendra-wordmark-horizontal": [None],        # 1200×300 native
    "dendra-wordmark-horizontal-dark": [None],
    "dendra-wordmark-stacked": [None],           # 600×720 native
    "dendra-wordmark-stacked-dark": [None],
    "dendra-social-card": [None],                # 1200×630 native
    "dendra-social-card-dark": [None],
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
