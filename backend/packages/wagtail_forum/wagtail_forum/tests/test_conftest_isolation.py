"""Regression guard for the autouse fixture in ``tests/conftest.py`` (todo 511).

``_without_host_override_providers`` empties ``conf._override_providers`` for
every package test (todo 501). Without a test of its own, deleting it would
leave the full suite green: an earlier DB test warms the host provider's memo,
so only a lone-file run of ``test_spam.py`` would go red, and nothing in CI
runs that.

These tests go red in the full suite too. The host registers its provider at
``AppConfig.ready()``, so ``_override_providers`` is non-empty at import time
in any run order, and only the fixture can empty it.
"""

import pathlib
import re

import pytest
from wagtail_forum import conf


@pytest.fixture(scope="module")
def providers_before_fixture():
    """The provider list as the host left it, captured outside the fixture.

    A module-scoped fixture is set up before the function-scoped autouse one,
    so this sees the list before ``conftest`` empties it. Its teardown runs
    after the autouse fixture's last restore, so it also checks that the list
    was put back as it was.
    """
    captured = list(conf._override_providers)
    yield captured
    assert (
        conf._override_providers == captured
    ), "conftest did not restore conf._override_providers after the test"


def test_package_tests_run_without_host_override_providers(providers_before_fixture):
    if not providers_before_fixture:
        pytest.skip("no host override provider is registered in this project")

    assert conf._override_providers == []
    for provider in providers_before_fixture:
        assert provider not in conf._override_providers


def test_conftest_imports_nothing_from_the_host():
    # test_reusability skips tests/, so it does not cover the conftest.
    conftest = pathlib.Path(__file__).with_name("conftest.py")
    host_import = re.compile(r"^\s*(from|import)\s+apps(\.|\s|$)", re.MULTILINE)

    assert not host_import.search(conftest.read_text(encoding="utf-8"))
