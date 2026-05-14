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

"""Public registry contributions.

The third Tier of the Shared Package strategy: a community-contributed
registry of analyzed repos with curated fixes. Contributions are
opt-in and stripped of identifying information before upload — the
client-side ``anonymize`` pass strips a conservative key list and the
server re-validates that the same keys are absent before accepting.
"""

from __future__ import annotations

import os
from typing import Any

import requests

from postrule import auth
from postrule.cloud import API_BASE_URL, NotLoggedInError

__all__ = ["anonymize", "contribute_anonymized"]

_TIMEOUT_SECONDS = 10.0

# Keys we strip from any submitted corpus before it leaves the machine.
# Conservative default, expanded as we learn what's leaking.
_IDENTIFYING_KEYS = frozenset(
    {
        "author",
        "email",
        "user",
        "username",
        "owner",
        "repo_url",
        "remote_url",
        "absolute_path",
        "abs_path",
        "host",
        "hostname",
        "machine_id",
    }
)


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


def anonymize(corpus_dict: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the corpus with identifying keys stripped."""

    def _scrub(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: _scrub(v) for k, v in obj.items() if k not in _IDENTIFYING_KEYS}
        if isinstance(obj, list):
            return [_scrub(v) for v in obj]
        return obj

    scrubbed = _scrub(corpus_dict)
    # Type checker comfort: top-level is dict-in, dict-out.
    assert isinstance(scrubbed, dict)
    return scrubbed


def contribute_anonymized(corpus_dict: dict[str, Any]) -> bool:
    """Strip identifying info, then upload to the public registry."""
    headers = _auth_headers()
    payload = anonymize(corpus_dict)
    url = f"{_api_base()}/registry/contribute"
    resp = requests.post(url, json=payload, headers=headers, timeout=_TIMEOUT_SECONDS)
    return bool(getattr(resp, "ok", False))
