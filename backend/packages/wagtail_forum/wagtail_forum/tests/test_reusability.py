import pathlib
import re

import pytest
import wagtail_forum

# An ``import``/``from`` statement for the host's ``apps`` namespace, or a
# quoted ``apps.`` dotted path: ``pytest_plugins``, ``importlib.import_module``
# and ``__import__`` load a host module that way, with no import statement.
# A comma import (``import x, apps.y``) is not matched; isort (pre-commit)
# splits it onto separate lines. test_conftest_isolation runs the same
# pattern over ``tests/conftest.py``.
HOST_IMPORT = re.compile(r"^\s*(from|import)\s+apps(\.|\s|$)|['\"]apps\.", re.MULTILINE)


def test_package_never_imports_host_apps_namespace():
    root = pathlib.Path(wagtail_forum.__file__).resolve().parent
    offenders = []
    for py in root.rglob("*.py"):
        if "tests" in py.parts or "migrations" in py.parts:
            continue
        if HOST_IMPORT.search(py.read_text(encoding="utf-8")):
            offenders.append(str(py.relative_to(root)))
    assert offenders == [], f"package imports host 'apps.*': {offenders}"


@pytest.mark.parametrize(
    "source",
    [
        "from apps.forum_host import forum_settings",
        "import apps.forum_host",
        "    import apps",
        'pytest_plugins = ["apps.forum_host.fixtures"]',
        "importlib.import_module('apps.forum_host.forum_settings')",
    ],
)
def test_host_import_flags_imports_and_quoted_host_paths(source):
    assert HOST_IMPORT.search(source)


@pytest.mark.parametrize(
    "source",
    [
        "from django.apps import apps",
        "import django.apps",
        "apps.get_app_config('wagtail_forum')",
        'label = "myapps.thing"',
        "the host's provider (``apps.forum_host.forum_settings.provide``)",
    ],
)
def test_host_import_ignores_text_that_loads_no_host_module(source):
    assert not HOST_IMPORT.search(source)
