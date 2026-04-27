#!/usr/bin/env python3
# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: Apache-2.0

"""Drive a headless Chromium against localhost:8000 and capture
landing-page screenshots for visual review.

Outputs:
- /tmp/landing-full.png        full-page screenshot
- /tmp/landing-try.png         the analyzer-demo panel
- /tmp/landing-expanded.png    a single expanded-row panel
- /tmp/landing-install.png     the install walkthrough section

Run from repo root:
    .venv/bin/python scripts/screenshot_landing.py
"""

from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

URL = "http://localhost:8000/"


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
        )
        page = ctx.new_page()
        page.goto(URL, wait_until="networkidle")
        # Trigger expansion of the first site row so we capture the panel.
        page.wait_for_selector(".site-row", timeout=5000)
        # Wait for the marimo preset to load + table render
        page.wait_for_function(
            "document.querySelectorAll('.site-row').length > 0",
            timeout=5000,
        )

        # Full page first (no expansion).
        page.screenshot(path="/tmp/landing-full.png", full_page=True)
        print("wrote /tmp/landing-full.png")

        # Try-panel only.
        try_panel = page.query_selector("[data-analyzer-demo]")
        if try_panel:
            try_panel.screenshot(path="/tmp/landing-try.png")
            print("wrote /tmp/landing-try.png")

        # Click the first site row to expand.
        first_row = page.query_selector(".site-row")
        if first_row:
            first_row.click()
            page.wait_for_timeout(300)
            expansion = page.query_selector(".site-expanded")
            if expansion:
                expansion.screenshot(path="/tmp/landing-expanded.png")
                print("wrote /tmp/landing-expanded.png")
            # Click each tab in turn and capture.
            for tab_name, out in (
                ("wrapped", "/tmp/landing-tab-wrapped.png"),
                ("log", "/tmp/landing-tab-log.png"),
                ("config", "/tmp/landing-tab-config.png"),
            ):
                tab_btn = page.query_selector(f".site-tab[data-tab='{tab_name}']")
                if tab_btn:
                    tab_btn.click()
                    page.wait_for_timeout(150)
                    expansion2 = page.query_selector(".site-expanded")
                    if expansion2:
                        expansion2.screenshot(path=out)
                        print(f"wrote {out}")

        # Install walkthrough.
        install = page.query_selector("#install")
        if install:
            install.scroll_into_view_if_needed()
            page.wait_for_timeout(150)
            install.screenshot(path="/tmp/landing-install.png")
            print("wrote /tmp/landing-install.png")

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
