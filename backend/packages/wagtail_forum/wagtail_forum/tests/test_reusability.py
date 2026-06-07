import pathlib
import re

import wagtail_forum

HOST_IMPORT = re.compile(r"^\s*(from|import)\s+apps(\.|\s|$)", re.MULTILINE)


def test_package_never_imports_host_apps_namespace():
    root = pathlib.Path(wagtail_forum.__file__).resolve().parent
    offenders = []
    for py in root.rglob("*.py"):
        if "tests" in py.parts or "migrations" in py.parts:
            continue
        if HOST_IMPORT.search(py.read_text(encoding="utf-8")):
            offenders.append(str(py.relative_to(root)))
    assert offenders == [], f"package imports host 'apps.*': {offenders}"
