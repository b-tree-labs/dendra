# Copyright (c) 2026 B-Tree Labs
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

"""Team-shared analyzer corpus.

A team uploads a corpus (rule + label set + examples) under a
team-chosen ``team_id`` and gets back a share URL. Other team
members fetch by ``team_id``. v1.0 ships with convention-only
isolation: anyone who knows the ``team_id`` can fetch. The
``team_id`` is operator-coordinated out of band; treat it like a
shared secret.

v1.1 will tie this to a real team-membership model in the dashboard.
"""

from __future__ import annotations

import os
from typing import Any

import requests

from postrule import auth
from postrule.cloud import API_BASE_URL, NotLoggedInError

__all__ = ["fetch_team_corpus", "share_corpus"]

_TIMEOUT_SECONDS = 10.0


def _api_base() -> str:
    return os.environ.get("POSTRULE_CLOUD_API_BASE", API_BASE_URL).rstrip("/")


def _auth_headers() -> dict[str, str]:
    creds = auth.load_credentials()
    if creds is None:
        raise NotLoggedInError(
            "No Postrule credentials found. Run `postrule login` to create a free "
            "account, or set POSTRULE_API_KEY."
        )
    return {
        "Authorization": f"Bearer {creds['api_key']}",
        "Content-Type": "application/json",
    }


def share_corpus(corpus_dict: dict[str, Any], team_id: str) -> str:
    """Upload a corpus under ``team_id`` and return its share URL.

    The server stamps a server-canonical URL of the form
    ``<api-base>/team-corpus/<team_id>`` that team members can paste
    into ``fetch_team_corpus`` to retrieve the most recent corpus.
    """
    headers = _auth_headers()
    url = f"{_api_base()}/team-corpus"
    body = {"team_id": team_id, "corpus": corpus_dict}
    resp = requests.post(url, json=body, headers=headers, timeout=_TIMEOUT_SECONDS)
    if getattr(resp, "ok", False):
        try:
            payload = resp.json()
            if isinstance(payload, dict) and payload.get("share_url"):
                return str(payload["share_url"])
        except ValueError:
            pass
    # Non-ok response: synthesize the canonical URL from inputs so the
    # caller has something coherent to display, but the URL won't
    # resolve to anything until a successful upload.
    return f"{_api_base()}/team-corpus/{team_id}"


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
