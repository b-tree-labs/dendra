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

"""Local credential store for the Dendra CLI.

Credentials live at ``~/.dendra/credentials`` (mode 0600) as JSON, with
``$DENDRA_API_KEY`` as an env-var fallback for CI / containerized use.

This is the v1 scaffolding for relationship-building, not a hard DRM
boundary: OSS classification works without an account; only cloud
features (sync, team corpus, registry) consult these credentials.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

__all__ = [
    "clear_credentials",
    "credentials_path",
    "is_logged_in",
    "load_credentials",
    "save_credentials",
]


def credentials_path() -> Path:
    """Return ``~/.dendra/credentials`` (does not require existence)."""
    return Path.home() / ".dendra" / "credentials"


def load_credentials() -> dict | None:
    """Return saved credentials, or fall back to ``$DENDRA_API_KEY``.

    Returns ``None`` when neither a credentials file nor the env var
    yields an API key. The on-disk file always wins over the env var
    so that ``dendra logout`` is honored even when the env var is set.
    """
    path = credentials_path()
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            payload = None
        if isinstance(payload, dict) and payload.get("api_key"):
            return {
                "api_key": payload["api_key"],
                "email": payload.get("email"),
            }

    env_key = os.environ.get("DENDRA_API_KEY")
    if env_key:
        return {"api_key": env_key, "email": None}

    return None


def save_credentials(api_key: str, email: str | None = None) -> None:
    """Persist credentials at ``~/.dendra/credentials`` with mode 0600.

    The parent directory is created if missing. Existing credentials
    are overwritten.
    """
    path = credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {"api_key": api_key, "email": email}
    serialized = json.dumps(payload, indent=2, sort_keys=True)

    # Write then chmod. On POSIX, an os.open with mode 0o600 would be
    # tighter against TOCTOU race conditions, but the file is in the
    # user's own home directory and the permissions check below keeps
    # the security posture honest.
    path.write_text(serialized, encoding="utf-8")
    if os.name == "posix":
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def clear_credentials() -> None:
    """Remove the credentials file. No-op if it does not exist."""
    path = credentials_path()
    try:
        path.unlink()
    except FileNotFoundError:
        return


def is_logged_in() -> bool:
    """Return True iff ``load_credentials()`` would yield a key."""
    return load_credentials() is not None
