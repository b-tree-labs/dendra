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

"""Tests for ``dendra login`` — RFC 8628 device flow.

Mocks the requests layer + ``webbrowser`` + ``time.sleep`` so the
test suite stays offline and finishes in milliseconds.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from dendra import auth
from dendra.cli import _detect_device_name, cmd_login


@pytest.fixture()
def fake_home(tmp_path, monkeypatch):
    """Redirect ``Path.home()`` so credentials write to a tmp dir."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return tmp_path


@pytest.fixture()
def args(monkeypatch):
    """Default argparse-style namespace for cmd_login."""
    import argparse

    monkeypatch.setenv("DENDRA_API_BASE", "http://api.test/v1")
    return argparse.Namespace(no_browser=True, device_name=None)


def _resp(status: int, body: dict) -> MagicMock:
    """Build a mocked ``requests.Response``."""
    r = MagicMock()
    r.status_code = status
    r.ok = 200 <= status < 300
    r.json.return_value = body
    r.text = str(body)
    return r


class TestHappyPath:
    def test_full_flow_writes_credentials(self, args, fake_home):
        start_resp = _resp(
            200,
            {
                "device_code": "device-code-secret",
                "user_code": "ABCD-2345",
                "verification_uri": "http://app.test/cli-auth",
                "verification_uri_complete": "http://app.test/cli-auth?user_code=ABCD-2345",
                "expires_in": 900,
                "interval": 5,
            },
        )
        # First poll = pending; second poll = success.
        pending_resp = _resp(400, {"error": "authorization_pending"})
        success_resp = _resp(
            200,
            {
                "api_key": "dndr_live_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # pragma: allowlist secret
                "email": "user@example.com",
            },
        )

        with (
            patch("requests.post", side_effect=[start_resp, pending_resp, success_resp]) as post,
            patch("time.sleep"),
        ):
            rc = cmd_login(args)

        assert rc == 0
        # Three POSTs: /device/code + 2× /device/token
        assert post.call_count == 3
        assert post.call_args_list[0].args[0].endswith("/device/code")
        assert post.call_args_list[1].args[0].endswith("/device/token")
        assert post.call_args_list[2].args[0].endswith("/device/token")
        # Body of the start call carries the device_name override (or auto-detected).
        assert "device_name" in post.call_args_list[0].kwargs["json"]

        # Credentials were saved.
        creds = auth.load_credentials()
        assert creds is not None
        assert creds["api_key"].startswith("dndr_live_")
        assert creds["email"] == "user@example.com"


class TestErrorPaths:
    def test_start_network_error_returns_1(self, args, fake_home, capsys):
        with patch("requests.post", side_effect=requests.RequestException("dns boom")):
            rc = cmd_login(args)
        assert rc == 1
        assert "Could not reach Dendra" in capsys.readouterr().err

    def test_start_non_200_returns_1(self, args, fake_home, capsys):
        bad = _resp(503, {"error": "service_unavailable"})
        with patch("requests.post", return_value=bad):
            rc = cmd_login(args)
        assert rc == 1
        assert "Failed to start device flow" in capsys.readouterr().err

    def test_access_denied_during_poll_returns_1(self, args, fake_home, capsys):
        start_resp = _resp(
            200,
            {
                "device_code": "x",
                "user_code": "ABCD-2345",
                "verification_uri_complete": "http://app.test/cli-auth?user_code=ABCD-2345",
                "interval": 5,
                "expires_in": 900,
            },
        )
        denied = _resp(400, {"error": "access_denied"})
        with patch("requests.post", side_effect=[start_resp, denied]), patch("time.sleep"):
            rc = cmd_login(args)
        assert rc == 1
        assert "Access denied" in capsys.readouterr().err

    def test_expired_token_returns_1(self, args, fake_home, capsys):
        start_resp = _resp(
            200,
            {
                "device_code": "x",
                "user_code": "ABCD-2345",
                "verification_uri_complete": "http://app.test/cli-auth?user_code=ABCD-2345",
                "interval": 5,
                "expires_in": 900,
            },
        )
        expired = _resp(400, {"error": "expired_token"})
        with patch("requests.post", side_effect=[start_resp, expired]), patch("time.sleep"):
            rc = cmd_login(args)
        assert rc == 1
        assert "expired" in capsys.readouterr().err.lower()

    def test_invalid_grant_returns_1(self, args, fake_home, capsys):
        start_resp = _resp(
            200,
            {
                "device_code": "x",
                "user_code": "ABCD-2345",
                "verification_uri_complete": "http://app.test/cli-auth?user_code=ABCD-2345",
                "interval": 5,
                "expires_in": 900,
            },
        )
        bad = _resp(400, {"error": "invalid_grant"})
        with patch("requests.post", side_effect=[start_resp, bad]), patch("time.sleep"):
            rc = cmd_login(args)
        assert rc == 1
        assert "invalid_grant" in capsys.readouterr().err

    def test_keyboard_interrupt_returns_130(self, args, fake_home, capsys):
        start_resp = _resp(
            200,
            {
                "device_code": "x",
                "user_code": "ABCD-2345",
                "verification_uri_complete": "http://app.test/cli-auth?user_code=ABCD-2345",
                "interval": 5,
                "expires_in": 900,
            },
        )
        with (
            patch("requests.post", return_value=start_resp),
            patch("time.sleep", side_effect=KeyboardInterrupt),
        ):
            rc = cmd_login(args)
        assert rc == 130
        assert "cancelled" in capsys.readouterr().err.lower()

    def test_slow_down_increases_interval(self, args, fake_home):
        start_resp = _resp(
            200,
            {
                "device_code": "x",
                "user_code": "ABCD-2345",
                "verification_uri_complete": "http://app.test/cli-auth?user_code=ABCD-2345",
                "interval": 5,
                "expires_in": 900,
            },
        )
        slow = _resp(400, {"error": "slow_down"})
        success = _resp(
            200,
            {
                "api_key": "dndr_live_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # pragma: allowlist secret
                "email": "u@e.com",
            },
        )
        sleep_calls: list[float] = []
        with (
            patch("requests.post", side_effect=[start_resp, slow, success]),
            patch("time.sleep", side_effect=lambda s: sleep_calls.append(s)),
        ):
            rc = cmd_login(args)
        assert rc == 0
        # First poll-cycle waits the initial 5s; after slow_down the second
        # cycle waits ≥ 10s (server bumped us). Three sleep calls total.
        assert len(sleep_calls) >= 2
        assert sleep_calls[0] == 5.0
        assert sleep_calls[1] >= 10.0


class TestPolish:
    def test_no_browser_flag_skips_open(self, args, fake_home):
        start_resp = _resp(
            200,
            {
                "device_code": "x",
                "user_code": "ABCD-2345",
                "verification_uri_complete": "http://app.test/cli-auth?user_code=ABCD-2345",
                "interval": 5,
                "expires_in": 900,
            },
        )
        success = _resp(
            200,
            {
                "api_key": "dndr_live_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # pragma: allowlist secret
                "email": "u@e.com",
            },
        )

        with (
            patch("requests.post", side_effect=[start_resp, success]),
            patch("time.sleep"),
            patch("webbrowser.open") as wb_open,
        ):
            args.no_browser = True
            rc = cmd_login(args)
        assert rc == 0
        wb_open.assert_not_called()

    def test_browser_open_failure_is_silent(self, args, fake_home):
        # If webbrowser.open raises (e.g. WSL with no DISPLAY) the flow
        # should continue, not crash.
        start_resp = _resp(
            200,
            {
                "device_code": "x",
                "user_code": "ABCD-2345",
                "verification_uri_complete": "http://app.test/cli-auth?user_code=ABCD-2345",
                "interval": 5,
                "expires_in": 900,
            },
        )
        success = _resp(
            200,
            {
                "api_key": "dndr_live_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # pragma: allowlist secret
                "email": "u@e.com",
            },
        )
        args.no_browser = False

        with (
            patch("requests.post", side_effect=[start_resp, success]),
            patch("time.sleep"),
            patch("webbrowser.open", side_effect=RuntimeError("no display")),
        ):
            rc = cmd_login(args)
        assert rc == 0  # webbrowser failure ignored

    def test_device_name_arg_overrides_hostname(self, args, fake_home):
        args.device_name = "ci-runner-7"
        start_resp = _resp(
            200,
            {
                "device_code": "x",
                "user_code": "ABCD-2345",
                "verification_uri_complete": "http://app.test/cli-auth?user_code=ABCD-2345",
                "interval": 5,
                "expires_in": 900,
            },
        )
        success = _resp(
            200,
            {
                "api_key": "dndr_live_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # pragma: allowlist secret
                "email": "u@e.com",
            },
        )
        with patch("requests.post", side_effect=[start_resp, success]) as post, patch("time.sleep"):
            cmd_login(args)
        body = post.call_args_list[0].kwargs["json"]
        assert body["device_name"] == "ci-runner-7"

    def test_min_interval_floored_at_2_seconds(self, args, fake_home):
        # Server advertises a 0.1s interval (misconfigured) — CLI must
        # floor to 2s to avoid hammering the server.
        start_resp = _resp(
            200,
            {
                "device_code": "x",
                "user_code": "ABCD-2345",
                "verification_uri_complete": "http://app.test/cli-auth?user_code=ABCD-2345",
                "interval": 0.1,
                "expires_in": 900,
            },
        )
        success = _resp(
            200,
            {
                "api_key": "dndr_live_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",  # pragma: allowlist secret
                "email": "u@e.com",
            },
        )
        sleeps: list[float] = []
        with (
            patch("requests.post", side_effect=[start_resp, success]),
            patch("time.sleep", side_effect=lambda s: sleeps.append(s)),
        ):
            cmd_login(args)
        assert sleeps[0] >= 2.0


class TestDetectDeviceName:
    def test_returns_hostname_stripped_of_dns_suffix(self, monkeypatch):
        monkeypatch.setattr("socket.gethostname", lambda: "ben-laptop.local")
        assert _detect_device_name() == "ben-laptop"

    def test_returns_unknown_on_empty_hostname(self, monkeypatch):
        monkeypatch.setattr("socket.gethostname", lambda: "")
        assert _detect_device_name() == "unknown"

    def test_returns_unknown_on_oserror(self, monkeypatch):
        def boom() -> str:
            raise OSError("no")

        monkeypatch.setattr("socket.gethostname", boom)
        assert _detect_device_name() == "unknown"

    def test_truncates_to_64_chars(self, monkeypatch):
        monkeypatch.setattr("socket.gethostname", lambda: "x" * 200)
        assert len(_detect_device_name()) == 64
