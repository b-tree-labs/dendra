# Copyright (c) 2026 B-Tree Ventures, LLC
# SPDX-License-Identifier: LicenseRef-BSL-1.1
#
# Licensed under the Business Source License 1.1 (the "License").
# You may not use this file except in compliance with the License.
# You may obtain a copy of the License at LICENSE-BSL in the
# repository root, or at https://mariadb.com/bsl11/.
#
# Change Date:    2030-05-01
# Change License: Apache License, Version 2.0
#
# Additional Use Grant: see LICENSE-BSL. Production use is
# permitted; offering a competing hosted service is not.

"""Team-shared analyzer corpus (v1 stub).

A team uploads a corpus (rule + label set + examples) and gets back a
share URL. Other team members fetch by team ID. Real implementation
will tie to the team-membership model in the dashboard.
"""

from __future__ import annotations

import os
from typing import Any

import requests

from dendra import auth
from dendra.cloud import API_BASE_URL, NotLoggedInError

__all__ = ["fetch_team_corpus", "share_corpus"]

_TIMEOUT_SECONDS = 10.0


def _api_base() -> str:
    return os.environ.get("DENDRA_CLOUD_API_BASE", API_BASE_URL).rstrip("/")


def _auth_headers() -> dict[str, str]:
    creds = auth.load_credentials()
    if creds is None:
        raise NotLoggedInError(
            "No Dendra credentials found. Run `dendra login` to create a free "
            "account, or set DENDRA_API_KEY."
        )
    return {
        "Authorization": f"Bearer {creds['api_key']}",
        "Content-Type": "application/json",
    }


def share_corpus(corpus_dict: dict[str, Any]) -> str:
    """Upload a corpus and return its share URL.

    Falls back to a synthesized URL if the response shape is unexpected,
    so callers always have something to display.
    """
    headers = _auth_headers()
    url = f"{_api_base()}/team-corpus"
    resp = requests.post(url, json=corpus_dict, headers=headers, timeout=_TIMEOUT_SECONDS)
    if getattr(resp, "ok", False):
        try:
            payload = resp.json()
            if isinstance(payload, dict) and payload.get("share_url"):
                return str(payload["share_url"])
        except ValueError:
            pass
    return f"{_api_base()}/team-corpus/pending"


def fetch_team_corpus(team_id: str) -> dict:
    """Fetch the most recent shared corpus for a team."""
    headers = _auth_headers()
    url = f"{_api_base()}/team-corpus/{team_id}"
    resp = requests.get(url, headers=headers, timeout=_TIMEOUT_SECONDS)
    if not getattr(resp, "ok", False):
        return {}
    try:
        data = resp.json()
        return data if isinstance(data, dict) else {}
    except ValueError:
        return {}
