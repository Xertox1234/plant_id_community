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

import pytest
from django.apps import apps
from wagtail_forum import conf

from .test_reusability import HOST_IMPORT


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


def provider_verdict(providers, host_installed):
    """``"skip"``, ``"fail"`` or ``"check"`` for the provider list the host left.

    apps.forum_host registers its provider at ready(), so where it is
    installed an empty list means that registration is gone, or an earlier
    test removed it without putting it back: fail, since a skip would hide a
    deleted fixture (todo 523). The strict check covers only apps.forum_host:
    for any other host an empty list cannot tell "registers none" from
    "lost", so it still skips.
    """
    if providers:
        return "check"
    return "fail" if host_installed else "skip"


def test_package_tests_run_without_host_override_providers(providers_before_fixture):
    verdict = provider_verdict(
        providers_before_fixture, apps.is_installed("apps.forum_host")
    )
    if verdict == "skip":
        pytest.skip("no host override provider is registered in this project")

    assert verdict == "check", (
        "apps.forum_host is installed, but conf._override_providers was empty "
        "before the conftest fixture ran: its ready() registration is gone, or "
        "an earlier test unregistered it without restoring it (todo 523)"
    )
    assert conf._override_providers == []


@pytest.mark.parametrize(
    ("providers", "host_installed", "expected"),
    [
        ([], False, "skip"),
        ([], True, "fail"),
        ([object()], True, "check"),
        ([object()], False, "check"),
    ],
)
def test_provider_verdict_arms(providers, host_installed, expected):
    # Pins todo 523's fail-instead-of-skip arm with synthetic inputs: a
    # healthy run never feeds the guard an empty list (todo 560).
    assert provider_verdict(providers, host_installed) == expected


def test_conftest_imports_nothing_from_the_host():
    # test_reusability skips tests/, so it does not cover the conftest. The
    # pattern is that test's, so tightening it tightens this check too.
    conftest = pathlib.Path(__file__).with_name("conftest.py")

    assert not HOST_IMPORT.search(conftest.read_text(encoding="utf-8"))
