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

"""Cloud-synced switch configurations (v1 stub).

The dashboard (``cloud/dashboard``) exposes ``/api/switches`` endpoints
that this module talks to. Until the dashboard ships, these calls are
expected to be mocked in tests; live calls will return whatever the
v1 stub endpoint returns.
"""

from __future__ import annotations

import os
from typing import Any

import requests

from dendra import auth
from dendra.cloud import API_BASE_URL, NotLoggedInError

__all__ = ["pull_switch_config", "push_switch_config"]

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


def push_switch_config(config: dict[str, Any]) -> bool:
    """Push a switch configuration to the cloud.

    Returns ``True`` on HTTP success, ``False`` on any non-2xx response.
    Raises :class:`NotLoggedInError` if no credentials are available.
    """
    headers = _auth_headers()
    url = f"{_api_base()}/switches"
    resp = requests.post(url, json=config, headers=headers, timeout=_TIMEOUT_SECONDS)
    return bool(getattr(resp, "ok", False))


def pull_switch_config(name: str) -> dict | None:
    """Fetch a named switch configuration from the cloud.

    Returns the config dict, or ``None`` on 404 / error. Raises
    :class:`NotLoggedInError` if no credentials are available.
    """
    headers = _auth_headers()
    url = f"{_api_base()}/switches/{name}"
    resp = requests.get(url, headers=headers, timeout=_TIMEOUT_SECONDS)
    if not getattr(resp, "ok", False):
        return None
    try:
        return resp.json()
    except ValueError:
        return None
