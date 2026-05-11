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

"""Tests for ``dendra.auth`` — local credential storage + env fallback."""

from __future__ import annotations

import json
import os
import stat

import pytest

from dendra import auth


@pytest.fixture()
def fake_home(tmp_path, monkeypatch):
    """Redirect ``~`` to a tmp dir so credentials never touch the real home."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Some platforms also consult USERPROFILE; mirror it so Path.home() agrees.
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    # Drop any ambient API key from the parent shell.
    monkeypatch.delenv("DENDRA_API_KEY", raising=False)
    return tmp_path


class TestLoadCredentials:
    def test_returns_none_when_no_file_and_no_env(self, fake_home):
        assert auth.load_credentials() is None

    def test_returns_creds_from_file(self, fake_home):
        auth.save_credentials("dndra_abc123", email="user@example.com")
        creds = auth.load_credentials()
        assert creds is not None
        assert creds["api_key"] == "dndra_abc123"  # pragma: allowlist secret
        assert creds["email"] == "user@example.com"

    def test_env_var_fallback(self, fake_home, monkeypatch):
        monkeypatch.setenv("DENDRA_API_KEY", "dndra_envkey")
        creds = auth.load_credentials()
        assert creds is not None
        assert creds["api_key"] == "dndra_envkey"  # pragma: allowlist secret
        # Email is unknown when only the env var is set.
        assert creds.get("email") is None

    def test_file_takes_precedence_over_env(self, fake_home, monkeypatch):
        auth.save_credentials("dndra_filekey", email="u@x.com")
        monkeypatch.setenv("DENDRA_API_KEY", "dndra_envkey")
        creds = auth.load_credentials()
        assert creds["api_key"] == "dndra_filekey"  # pragma: allowlist secret


class TestSaveCredentials:
    def test_round_trip(self, fake_home):
        auth.save_credentials("dndra_token", email="a@b.com")
        creds = auth.load_credentials()
        # `telemetry_enabled` defaults to True (Q4 decision 2026-05-11).
        assert creds == {
            "api_key": "dndra_token",  # pragma: allowlist secret
            "email": "a@b.com",
            "telemetry_enabled": True,
        }

    def test_file_permissions_are_0600(self, fake_home):
        auth.save_credentials("dndra_token", email="a@b.com")
        cred_path = fake_home / ".dendra" / "credentials"
        assert cred_path.exists()
        # On POSIX, the mode bits should be exactly user-read/user-write.
        if os.name == "posix":
            mode = stat.S_IMODE(cred_path.stat().st_mode)
            assert mode == 0o600, f"expected 0600, got {oct(mode)}"

    def test_file_contents_are_valid_json(self, fake_home):
        auth.save_credentials("dndra_token", email="a@b.com")
        cred_path = fake_home / ".dendra" / "credentials"
        # JSON is a subset of TOML for plain key/value, but the canonical
        # on-disk format we ship is JSON. Make sure it parses.
        payload = json.loads(cred_path.read_text(encoding="utf-8"))
        assert payload["api_key"] == "dndra_token"  # pragma: allowlist secret

    def test_overwrites_existing_credentials(self, fake_home):
        auth.save_credentials("dndra_old", email="old@x.com")
        auth.save_credentials("dndra_new", email="new@x.com")
        creds = auth.load_credentials()
        assert creds["api_key"] == "dndra_new"  # pragma: allowlist secret
        assert creds["email"] == "new@x.com"


class TestClearCredentials:
    def test_removes_credentials_file(self, fake_home):
        auth.save_credentials("dndra_token", email="a@b.com")
        cred_path = fake_home / ".dendra" / "credentials"
        assert cred_path.exists()
        auth.clear_credentials()
        assert not cred_path.exists()

    def test_clear_when_no_file_is_a_noop(self, fake_home):
        # Should not raise.
        auth.clear_credentials()


class TestIsLoggedIn:
    def test_false_when_no_credentials(self, fake_home):
        assert auth.is_logged_in() is False

    def test_true_with_file_credentials(self, fake_home):
        auth.save_credentials("dndra_token", email="a@b.com")
        assert auth.is_logged_in() is True

    def test_true_with_env_credentials(self, fake_home, monkeypatch):
        monkeypatch.setenv("DENDRA_API_KEY", "dndra_env")
        assert auth.is_logged_in() is True


class TestTelemetryPreference:
    """The cached `telemetry_enabled` flag round-trips, defaults to True
    on pre-existing credentials files (no field), and can be refreshed
    in-place via `update_telemetry_preference`."""

    def test_save_with_telemetry_disabled(self, fake_home):
        auth.save_credentials("dndra_off", email="a@b.com", telemetry_enabled=False)
        creds = auth.load_credentials()
        assert creds is not None
        assert creds["telemetry_enabled"] is False

    def test_save_default_is_telemetry_enabled(self, fake_home):
        auth.save_credentials("dndra_on", email="a@b.com")
        creds = auth.load_credentials()
        assert creds is not None
        assert creds["telemetry_enabled"] is True

    def test_legacy_credentials_default_to_telemetry_enabled(self, fake_home):
        # Simulate a pre-1.0 credentials file written without the field.
        path = auth.credentials_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        legacy_payload = {"api_key": "dndra_legacy", "email": "a@b.com"}  # pragma: allowlist secret
        path.write_text(json.dumps(legacy_payload), encoding="utf-8")
        creds = auth.load_credentials()
        assert creds is not None
        assert creds["telemetry_enabled"] is True

    def test_env_var_only_defaults_to_telemetry_enabled(self, fake_home, monkeypatch):
        monkeypatch.setenv("DENDRA_API_KEY", "dndra_env")
        creds = auth.load_credentials()
        assert creds is not None
        assert creds["telemetry_enabled"] is True

    def test_update_telemetry_preference_persists(self, fake_home):
        auth.save_credentials("dndra_tok", email="a@b.com", telemetry_enabled=True)
        assert auth.update_telemetry_preference(False) is True
        creds = auth.load_credentials()
        assert creds["telemetry_enabled"] is False
        # API key + email survive the refresh.
        assert creds["api_key"] == "dndra_tok"  # pragma: allowlist secret
        assert creds["email"] == "a@b.com"

    def test_update_telemetry_preference_no_creds_is_noop(self, fake_home):
        assert auth.update_telemetry_preference(False) is False
