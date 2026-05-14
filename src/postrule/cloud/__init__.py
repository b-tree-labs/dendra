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

"""Postrule cloud features.

Three opt-in modules sit alongside the OSS package:

- ``postrule.cloud.sync`` — push / pull switch configurations.
- ``postrule.cloud.team_corpus`` — share analyzer corpora across a team.
- ``postrule.cloud.registry`` — contribute anonymized corpora to the
  public registry.

All three require a logged-in account (see ``postrule.auth``) and raise
:class:`NotLoggedInError` when no credentials are present. The HTTP
endpoints they hit are mounted on the production api Worker at
``api.postrule.ai/v1/*``. Override the base URL with the
``POSTRULE_CLOUD_API_BASE`` environment variable for local dev.
"""

from __future__ import annotations

__all__ = ["API_BASE_URL", "NotLoggedInError", "__version__"]

__version__ = "0.1.0"

# Override with ``POSTRULE_CLOUD_API_BASE`` for local dashboard dev.
API_BASE_URL = "https://api.postrule.ai/v1"


class NotLoggedInError(RuntimeError):
    """Raised when a cloud feature is invoked without credentials."""
