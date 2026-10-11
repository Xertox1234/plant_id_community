import pathlib
import re

import pytest
import wagtail_forum

# What this matches (todo 560):
# - an ``import``/``from`` statement for the host's ``apps`` namespace that
#   starts its line (after indentation), on any line of the file;
# - a quoted dotted ``apps.`` path anywhere, which is how ``pytest_plugins``
#   and ``importlib.import_module("apps.x")`` load a host module with no
#   import statement. A quoted host path counts as a host import.
# What it does not match: an import that does not start its line
# (``import os; import apps.x``, ``if X: from apps.y import z``), a comma
# import (``import x, apps.y``), and a load whose string is not a dotted
# ``apps.`` path (``__import__("apps", fromlist=[...])``,
# ``import_module(".forum_host", "apps")``). isort and flake8 (pre-commit)
# split the first two onto their own lines for backend/.
# Known false positive: quoted prose that opens with ``apps.`` (a comment
# ``# see 'apps.py'``) matches; reword it. The regex stays this narrow on
# purpose (owner decision 2026-10-11, todo 560).
# test_conftest_isolation runs the same pattern over ``tests/conftest.py``.
HOST_IMPORT = re.compile(r"^\s*(from|import)\s+apps(\.|\s|$)|['\"]apps\.", re.MULTILINE)


def host_import_lines(source):
    """1-based line numbers of every HOST_IMPORT hit in ``source``."""
    lines = []
    for match in HOST_IMPORT.finditer(source):
        # ``^\s*`` can start on a blank line above the statement; count
        # from the keyword, not from the match start.
        start = match.start(1) if match.group(1) else match.start()
        lines.append(source.count("\n", 0, start) + 1)
    return lines


def test_package_never_imports_host_apps_namespace():
    root = pathlib.Path(wagtail_forum.__file__).resolve().parent
    offenders = []
    for py in root.rglob("*.py"):
        if "tests" in py.parts or "migrations" in py.parts:
            continue
        rel = py.relative_to(root)
        for line in host_import_lines(py.read_text(encoding="utf-8")):
            offenders.append(f"{rel}:{line}")
    assert offenders == [], (
        "package imports host 'apps.*' (an import statement, or a quoted "
        f"'apps.' dotted path, which counts too): {offenders}"
    )


@pytest.mark.parametrize(
    "source",
    [
        "from apps.forum_host import forum_settings",
        "import apps.forum_host",
        "    import apps",
        'pytest_plugins = ["apps.forum_host.fixtures"]',
        "importlib.import_module('apps.forum_host.forum_settings')",
        # A module header: the host import is not on the first line, so
        # this pins re.MULTILINE (todo 560).
        "import pytest\n\nfrom apps.forum_host import x\n",
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
        # Pins the statement branch's boundary group (todo 560).
        "from appstore import x",
        # Pins the quoted branch's dot (todo 560).
        'x = "apps"',
    ],
)
def test_host_import_ignores_text_that_loads_no_host_module(source):
    assert not HOST_IMPORT.search(source)


@pytest.mark.parametrize(
    "source",
    [
        "__import__('apps', fromlist=['forum_host'])",
        "importlib.import_module('.forum_host', 'apps')",
        "import os; import apps.x",
        "if X: from apps.y import z",
    ],
)
def test_host_import_known_misses(source):
    # Documented edges, not wanted behaviour: the comment above HOST_IMPORT
    # names each one. If the pattern grows to catch one, update that comment.
    assert not HOST_IMPORT.search(source)


def test_host_import_known_false_positive_quoted_prose():
    # Quoted prose that opens with ``apps.`` matches. Kept on purpose: the
    # owner decided not to widen or rework the regex (todo 560).
    assert HOST_IMPORT.search("# see 'apps.py'")


def test_host_import_lines_names_the_line_of_each_hit():
    source = "import pytest\n\nfrom apps.forum_host import x\nX = 'apps.y'\n"

    assert host_import_lines(source) == [3, 4]
