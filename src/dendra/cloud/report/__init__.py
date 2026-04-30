# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: LicenseRef-BSL-1.1
#
# Licensed under the Business Source License 1.1. See LICENSE-BSL in
# the repository root, or https://mariadb.com/bsl11/.
#
# Change Date:    2030-05-01
# Change License: Apache License, Version 2.0
#
# Additional Use Grant: see LICENSE-BSL. Production use is permitted;
# offering a competing hosted service is not.

"""Per-switch + project-level report cards for Dendra graduations.

The report module is the customer-visible TDPD artifact: every wrapped
switch in a customer's repo gets a markdown report card at
``dendra/results/<switch>.md`` that fills in over time as outcomes
accumulate. The card shows the transition curve, the gate-fire
moment, the hypothesis-vs-observed verdict, and the cost trajectory.

Two top-level entry points:

- :func:`render_switch_card` — read storage for one switch, return
  rendered markdown.
- :func:`render_project_summary` — read storage for all known
  switches, return rendered project-summary markdown.

Storage agnostic: caller passes any object satisfying the
:class:`dendra.storage.Storage` protocol. The aggregator never writes
to storage; it's a read-only view.

Phase 1 (this release) ships markdown + Mermaid + checkpoint tables,
no PNG charts. Phase 2 adds matplotlib chart generation behind the
``dendra[viz]`` extra. The markdown templates have ``{transition_chart}``
slots that fill in once charts.py lands; without it those slots stay
as text placeholders and the markdown still reads cleanly.
"""

from __future__ import annotations

from dendra.cloud.report.aggregator import (
    Checkpoint,
    HypothesisVerdict,
    SwitchMetrics,
    aggregate_switch,
)
from dendra.cloud.report.render_markdown import render_switch_card

__all__ = [
    "Checkpoint",
    "HypothesisVerdict",
    "SwitchMetrics",
    "aggregate_switch",
    "render_switch_card",
]
