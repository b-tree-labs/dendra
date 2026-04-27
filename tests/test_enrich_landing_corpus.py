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

"""Tests for the test-suite filter in scripts/enrich_landing_corpus.py.

The enrich script regenerates the landing-page demo corpora and drops
test-suite false positives (functions like ``test_cors`` and
``test_links`` that the static analyzer otherwise flags as
classification sites). The filter has four signals:

  1. Function name matches ``^test_``.
  2. File path contains a test-suite fragment (``/tests/``, etc.).
  3. Function name is a unittest fixture method.
  4. Function takes zero arguments AND has no return statements.

Each signal needs a contract test: the script is called from the
landing-page CI, so a regression silently re-introduces low-quality
demo content.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT_PATH = Path(__file__).resolve().parent.parent / "scripts" / "enrich_landing_corpus.py"


@pytest.fixture(scope="module")
def enrich_mod():
    spec = importlib.util.spec_from_file_location("enrich_landing_corpus", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["enrich_landing_corpus"] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Name-based filter
# ---------------------------------------------------------------------------


class TestNameFilter:
    def test_pytest_prefix_caught(self, enrich_mod):
        assert enrich_mod._name_looks_like_test("test_cors")
        assert enrich_mod._name_looks_like_test("test_links")
        assert enrich_mod._name_looks_like_test("test_anything_at_all")

    def test_unittest_fixtures_caught(self, enrich_mod):
        for name in (
            "setUp",
            "tearDown",
            "setUpClass",
            "tearDownClass",
            "setUpModule",
            "tearDownModule",
        ):
            assert enrich_mod._name_looks_like_test(name), name

    def test_normal_names_pass(self, enrich_mod):
        assert not enrich_mod._name_looks_like_test("classify")
        assert not enrich_mod._name_looks_like_test("triage")
        # Don't catch "tested" or "testimonial" — only the literal prefix.
        assert not enrich_mod._name_looks_like_test("testimonial")
        # ``testing`` would be caught by ``^test_`` only if it had an
        # underscore. Bare ``testing`` is allowed through.
        assert not enrich_mod._name_looks_like_test("testing")


# ---------------------------------------------------------------------------
# Path-based filter
# ---------------------------------------------------------------------------


class TestPathFilter:
    @pytest.mark.parametrize(
        "path",
        [
            "tests/test_requests.py",
            "src/foo/tests/helpers.py",
            "src/foo/test/helpers.py",
            "src/foo/something_test.py",
            "src/foo/test_something.py",
            "tests/conftest.py",
            "src/foo/conftest.py",
        ],
    )
    def test_test_paths_caught(self, enrich_mod, path):
        assert enrich_mod._path_looks_like_test(path), path

    @pytest.mark.parametrize(
        "path",
        [
            "src/requests/utils.py",
            "dvc/info.py",
            "marimo/_runtime/runtime.py",
            "src/foo/protest.py",  # "test" in middle but not as a fragment
        ],
    )
    def test_production_paths_pass(self, enrich_mod, path):
        assert not enrich_mod._path_looks_like_test(path), path


# ---------------------------------------------------------------------------
# Zero-arg, no-return AST check
# ---------------------------------------------------------------------------


class TestZeroArgNoReturn:
    def test_zero_arg_no_return_caught(self, enrich_mod, tmp_path):
        src = tmp_path / "side_effects.py"
        src.write_text(
            "def run_thing():\n"
            "    print('hi')\n"
            "    if 'a':\n"
            "        print('a')\n"
            "    elif 'b':\n"
            "        print('b')\n",
            encoding="utf-8",
        )
        site = {
            "file_path": "side_effects.py",
            "function_name": "run_thing",
            "line_start": 1,
        }
        assert enrich_mod._is_zero_arg_no_return(tmp_path, site)

    def test_function_with_args_passes(self, enrich_mod, tmp_path):
        src = tmp_path / "classify.py"
        src.write_text(
            "def classify(x):\n    if x:\n        print('a')\n",
            encoding="utf-8",
        )
        site = {
            "file_path": "classify.py",
            "function_name": "classify",
            "line_start": 1,
        }
        assert not enrich_mod._is_zero_arg_no_return(tmp_path, site)

    def test_function_with_return_passes(self, enrich_mod, tmp_path):
        src = tmp_path / "classify.py"
        src.write_text(
            "def classify():\n    if True:\n        return 'a'\n    return 'b'\n",
            encoding="utf-8",
        )
        site = {
            "file_path": "classify.py",
            "function_name": "classify",
            "line_start": 1,
        }
        assert not enrich_mod._is_zero_arg_no_return(tmp_path, site)

    def test_starargs_count_as_args(self, enrich_mod, tmp_path):
        src = tmp_path / "wrap.py"
        src.write_text(
            "def runner(*args, **kwargs):\n    print(args, kwargs)\n",
            encoding="utf-8",
        )
        site = {
            "file_path": "wrap.py",
            "function_name": "runner",
            "line_start": 1,
        }
        # Has *args/**kwargs → not zero-arg, even though no return.
        assert not enrich_mod._is_zero_arg_no_return(tmp_path, site)

    def test_missing_file_returns_false(self, enrich_mod, tmp_path):
        site = {
            "file_path": "does/not/exist.py",
            "function_name": "anything",
            "line_start": 1,
        }
        # Conservative default: keep the site if we can't inspect it.
        assert not enrich_mod._is_zero_arg_no_return(tmp_path, site)


# ---------------------------------------------------------------------------
# End-to-end filter
# ---------------------------------------------------------------------------


class TestFilterTestSites:
    def test_drops_name_path_and_zero_arg(self, enrich_mod, tmp_path):
        src = tmp_path / "module.py"
        src.write_text(
            # line 1: side-effect function (will be hit by zero-arg rule)
            "def run_setup():\n"
            "    print('hi')\n"
            "\n"
            # line 4: classifier (kept)
            "def classify(x):\n"
            "    if x:\n"
            "        return 'a'\n"
            "    return 'b'\n",
            encoding="utf-8",
        )
        sites = [
            # 1: name match
            {
                "file_path": "module.py",
                "function_name": "test_cors",
                "line_start": 1,
            },
            # 2: path match
            {
                "file_path": "tests/test_requests.py",
                "function_name": "links",
                "line_start": 1,
            },
            # 3: zero-arg, no return
            {
                "file_path": "module.py",
                "function_name": "run_setup",
                "line_start": 1,
            },
            # 4: kept — real classifier
            {
                "file_path": "module.py",
                "function_name": "classify",
                "line_start": 4,
            },
        ]
        kept, counts = enrich_mod.filter_test_sites(sites, tmp_path, slug="demo")
        assert len(kept) == 1
        assert kept[0]["function_name"] == "classify"
        assert counts["name"] == 1
        assert counts["path"] == 1
        assert counts["zero-arg-no-return"] == 1
