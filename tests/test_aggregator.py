# Copyright (c) 2026 B-Tree Labs
# SPDX-License-Identifier: LicenseRef-BSL-1.1
#
# Unit tests for cloud/aggregator/run.py.
#
# The aggregator runs from raw stdlib (no `pip install` step in the
# nightly workflow), so this test imports it as a script via importlib.

from __future__ import annotations

import importlib.util
import io
import json
import urllib.error
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


def _http_error(code: int, msg: str = "") -> urllib.error.HTTPError:
    """Construct an HTTPError with a real fp (BytesIO) so that
    Python 3.14's stricter resource-deallocation pathway doesn't
    surface PytestUnraisableExceptionWarning at test teardown.
    """
    return urllib.error.HTTPError(
        url="u",
        code=code,
        msg=msg or "error",
        hdrs={},
        fp=io.BytesIO(b""),  # type: ignore[arg-type]
    )


_AGG_PATH = Path(__file__).resolve().parents[1] / "cloud" / "aggregator" / "run.py"
_spec = importlib.util.spec_from_file_location("aggregator_run", _AGG_PATH)
assert _spec is not None and _spec.loader is not None
aggregator_run = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aggregator_run)


# ---------------------------------------------------------------------------
# KV URL builders
# ---------------------------------------------------------------------------


class TestKvUrlBuilders:
    def test_put_url_shape(self) -> None:
        url = aggregator_run._kv_put_url("acct123", "nsXYZ", "tuned-defaults.json")
        assert url == (
            "https://api.cloudflare.com/client/v4/accounts/acct123"
            "/storage/kv/namespaces/nsXYZ/values/tuned-defaults.json"
        )

    def test_get_url_shape(self) -> None:
        url = aggregator_run._kv_get_url("acct123", "nsXYZ", "tuned-defaults.json")
        assert url == (
            "https://api.cloudflare.com/client/v4/accounts/acct123"
            "/storage/kv/namespaces/nsXYZ/values/tuned-defaults.json"
        )


# ---------------------------------------------------------------------------
# _put_to_kv: writes via PUT with bearer auth
# ---------------------------------------------------------------------------


def _fake_urlopen_response(status: int = 200, body: bytes = b"") -> MagicMock:
    """Build a context-manager-shaped urlopen response."""
    response = MagicMock()
    response.status = status
    response.read.return_value = body
    response.__enter__ = lambda s: s
    response.__exit__ = lambda *a: None
    return response


class TestPutToKv:
    def test_sends_put_with_bearer_and_body(self) -> None:
        captured: dict[str, Any] = {}

        def fake_urlopen(req: Any, timeout: float | None = None) -> Any:
            captured["url"] = req.full_url
            captured["method"] = req.get_method()
            captured["headers"] = dict(req.header_items())
            captured["body"] = req.data
            return _fake_urlopen_response(200)

        body = b'{"version": 5}'
        with patch.object(aggregator_run.urllib.request, "urlopen", fake_urlopen):
            aggregator_run._put_to_kv("acct1", "ns1", "tuned-defaults.json", body, "tok123")

        assert captured["method"] == "PUT"
        assert captured["body"] == body
        # urllib title-cases headers; compare case-insensitively.
        headers_lower = {k.lower(): v for k, v in captured["headers"].items()}
        assert headers_lower["authorization"] == "Bearer tok123"
        assert headers_lower["content-type"] == "application/json"
        assert (
            "/accounts/acct1/storage/kv/namespaces/ns1/values/tuned-defaults.json"
            in captured["url"]
        )

    def test_raises_on_non_2xx_status(self) -> None:
        with (
            patch.object(
                aggregator_run.urllib.request,
                "urlopen",
                return_value=_fake_urlopen_response(500),
            ),
            pytest.raises(RuntimeError, match="KV PUT failed"),
        ):
            aggregator_run._put_to_kv("a", "n", "k", b"{}", "t")


# ---------------------------------------------------------------------------
# _previous_version_kv: monotonic version via KV read
# ---------------------------------------------------------------------------


class TestPreviousVersionKv:
    def test_returns_version_from_existing_value(self) -> None:
        body = json.dumps({"version": 7, "cohort_size": 0}).encode("utf-8")
        with patch.object(
            aggregator_run.urllib.request,
            "urlopen",
            return_value=_fake_urlopen_response(200, body),
        ):
            v = aggregator_run._previous_version_kv("a", "n", "k", "tok")
        assert v == 7

    def test_returns_zero_when_kv_is_empty_404(self) -> None:
        with patch.object(
            aggregator_run.urllib.request,
            "urlopen",
            side_effect=_http_error(404, "Not Found"),
        ):
            v = aggregator_run._previous_version_kv("a", "n", "k", "tok")
        assert v == 0

    def test_returns_zero_on_garbage_body(self) -> None:
        with patch.object(
            aggregator_run.urllib.request,
            "urlopen",
            return_value=_fake_urlopen_response(200, b"not-json"),
        ):
            v = aggregator_run._previous_version_kv("a", "n", "k", "tok")
        assert v == 0


# ---------------------------------------------------------------------------
# _previous_version_from_file: pre-existing file path
# ---------------------------------------------------------------------------


class TestPreviousVersionFromFile:
    def test_returns_zero_when_file_missing(self, tmp_path: Path) -> None:
        assert aggregator_run._previous_version_from_file(tmp_path / "missing.json") == 0

    def test_reads_version_from_file(self, tmp_path: Path) -> None:
        p = tmp_path / "tuned.json"
        p.write_text(json.dumps({"version": 12}))
        assert aggregator_run._previous_version_from_file(p) == 12

    def test_returns_zero_on_corrupt_file(self, tmp_path: Path) -> None:
        p = tmp_path / "tuned.json"
        p.write_text("{not json")
        assert aggregator_run._previous_version_from_file(p) == 0


# ---------------------------------------------------------------------------
# _next_version: pure increment
# ---------------------------------------------------------------------------


class TestNextVersion:
    def test_increments_by_one(self) -> None:
        assert aggregator_run._next_version(0) == 1
        assert aggregator_run._next_version(41) == 42


# ---------------------------------------------------------------------------
# main(): KV path is taken when --kv-namespace-id is given
# ---------------------------------------------------------------------------


class TestMainKvPath:
    def test_main_writes_to_kv_when_flag_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "token-xyz")
        monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct-abc")

        # Stub the D1 query and the previous-version read so the test
        # focuses on main()'s flow control. Both helpers have direct
        # tests above; this is the wiring assertion.
        put_calls: list[dict[str, Any]] = []

        def fake_put_to_kv(
            account_id: str, namespace_id: str, key: str, body: bytes, token: str
        ) -> None:
            put_calls.append(
                {
                    "account_id": account_id,
                    "namespace_id": namespace_id,
                    "key": key,
                    "body": body,
                    "token": token,
                }
            )

        with (
            patch.object(aggregator_run, "query_d1", return_value=[]),
            patch.object(aggregator_run, "_previous_version_kv", return_value=0),
            patch.object(aggregator_run, "_put_to_kv", side_effect=fake_put_to_kv),
            patch.object(aggregator_run, "_git_sha", return_value="testsha"),
        ):
            rc = aggregator_run.main(
                argv=[
                    "--database",
                    "dendra-events-staging",
                    "--kv-namespace-id",
                    "ns-staging",
                ]
            )

        assert rc == 0
        assert len(put_calls) == 1
        call = put_calls[0]
        assert call["account_id"] == "acct-abc"
        assert call["namespace_id"] == "ns-staging"
        assert call["key"] == "tuned-defaults.json"
        assert call["token"] == "token-xyz"
        body = json.loads(call["body"].decode("utf-8"))
        # First write into an empty KV → version bumps to 1.
        assert body["version"] == 1
        assert body["cohort_size"] == 0

    def test_main_errors_when_kv_flag_without_credentials(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
        monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
        rc = aggregator_run.main(argv=["--kv-namespace-id", "ns-staging"])
        assert rc == 2
        err = capsys.readouterr().err
        assert "CLOUDFLARE_API_TOKEN" in err or "CLOUDFLARE_ACCOUNT_ID" in err
