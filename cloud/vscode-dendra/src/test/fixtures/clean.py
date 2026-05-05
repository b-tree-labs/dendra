# Copyright (c) 2026 B-Tree Labs
# SPDX-License-Identifier: Apache-2.0

"""Fixture: clean classifier (AUTO_LIFTABLE)."""


def triage(text: str) -> str:
    if "bug" in text:
        return "bug"
    if "feature" in text:
        return "feature"
    return "other"
