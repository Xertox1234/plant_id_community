"""The package under test is the one these tests ship with (todo 688).

The backend venv installs wagtail_forum editable from one checkout. A run from
another checkout (a git worktree) then imports that checkout's copy, and the
tests exercise code that is not the code being changed. backend/pytest.ini
puts packages/wagtail_forum on pytest's pythonpath so the copy beside these
tests wins.

The first test only tells the two copies apart in a worktree; in the main
checkout and in CI they are the same path. The second fails everywhere if the
pytest.ini entry is dropped.
"""

import sys
from pathlib import Path

import wagtail_forum


def test_wagtail_forum_is_imported_from_this_checkout() -> None:
    package_dir = Path(wagtail_forum.__file__).resolve().parent
    assert package_dir == Path(__file__).resolve().parent.parent


def test_package_root_is_on_pytest_pythonpath() -> None:
    package_root = Path(__file__).resolve().parents[2]
    entries = {Path(entry).resolve() for entry in sys.path if entry}
    assert package_root in entries
