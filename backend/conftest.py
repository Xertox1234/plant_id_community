"""Stamp the environment on every test result.

A test result is evidence about the environment that produced it, and until
this file existed nothing at the moment of the run said what that environment
was. Twice on 2026-09-08 that gap turned a real failure into "local noise"
(todos 378/379).

Two hooks, and both are load-bearing:

* ``pytest_report_header`` — the unconditional stamp. Makes no claim, so it has
  no false-positive budget to blow, and it gives a revert-control experiment
  the thing it lacked: two runs whose environment lines can be compared.
* ``pytest_terminal_summary`` — the drift warning, printed only when there is
  drift. This is the half that matters most: it lands next to "24 failed" at
  the bottom of the run, where the misreading actually happens, and unlike the
  header it survives ``-q``/``--no-header`` (``_pytest.terminal`` gates the
  header on ``verbosity >= 0``; the summary has no such gate).

Everything here fails open, **including the import of the checker itself**. A
broken environment check must never break a test run — that would be strictly
worse than the problem it reports. Each stamp line is computed under its own
guard, so a failure in the dependency comparison cannot also delete the
interpreter/tree lines.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_BACKEND = Path(__file__).parent


def _load_env_integrity():
    """Load the checker by file path, or return None.

    By file path rather than by adding ``apps/core`` to ``sys.path``: that shim
    would make every module beside it importable as a top-level name — `admin`,
    `models`, `views`, `security`, `exceptions`, `validators`, `middleware` —
    in every test run, shadowing any third-party package of the same name.

    Returning None instead of raising is the point. An unguarded
    ``exec_module`` here turns a missing or broken `env_integrity.py` into an
    ImportError during conftest collection, which aborts the entire suite with
    exit 4 and zero tests run. The shell hook already guards this same case
    with ``[ -f "$CHECKER" ] || exit 0``; this is the equivalent.
    """
    try:
        spec = importlib.util.spec_from_file_location(
            "_env_integrity", _BACKEND / "apps" / "core" / "env_integrity.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:  # noqa: BLE001 - a missing checker must not break the run
        return None


env_integrity = _load_env_integrity()


def _git(*args: str) -> str | None:
    """Run a git command, returning None on any failure.

    None and "" mean different things: "" is a successful command with no
    output (a clean tree), None is "could not determine". Collapsing the two
    would report a dirty tree as clean.
    """
    try:
        result = subprocess.run(
            ["git", *args], cwd=_BACKEND, capture_output=True, text=True, timeout=5
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _tree_state() -> str:
    """HEAD plus the uncommitted-file count, scoped to backend/.

    Scoped because this is a monorepo: an unscoped `git status` counts dirty
    files under web/, plant_community_mobile/ and the repo root, none of which
    affect a backend test result. An always-nonzero count is one a reader
    learns to ignore.

    A failed status reports "unknown", never 0. `docs/rules/testing.md` tells
    readers to compare this number across two runs to decide whether a revert
    control is valid, so a silent false zero would manufacture exactly the
    "you changed nothing that matters" misreading the rule exists to prevent.
    """
    head = _git("rev-parse", "--short", "HEAD") or "unknown"
    status = _git("status", "--porcelain", "--", ".")
    if status is None:
        dirty: object = "unknown"
    else:
        dirty = len([line for line in status.splitlines() if line.strip()])
    return f"HEAD {head}, {dirty} uncommitted file(s) under backend/"


def pytest_report_header(config):
    """Environment stamp. Each line is guarded separately."""
    lines = []
    try:
        lines.append(f"env: {sys.prefix}")
        lines.append(f"tree: {_tree_state()}")
    except Exception:  # noqa: BLE001
        pass
    try:
        pins = env_integrity.read_pins()
        installed = env_integrity.installed_versions()
        editable = env_integrity.editable_names()
        mismatched, missing, extra = env_integrity.compare(pins, installed, editable)
        lines.append(
            f"deps: {len(pins)} pinned, {len(mismatched)} mismatched, "
            f"{len(missing)} not installed, {len(extra)} unpinned"
        )
    except Exception:  # noqa: BLE001 - includes env_integrity being None
        lines.append("deps: unavailable (environment check could not run)")
    return lines


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Name the drifted packages, adjacent to the pass/fail counts."""
    # The whole body is guarded, not just the comparison: a write to a closed
    # stdout (BrokenPipeError) or a nonstandard TerminalReporter would
    # otherwise propagate out of a pytest hook and break the run this is
    # supposed to be annotating.
    try:
        lines = env_integrity.drift_report()
        if not lines:
            return
        terminalreporter.write_sep("=", "ENVIRONMENT DRIFT", red=True, bold=True)
        # sys.prefix, not "backend/venv": the comparison describes the
        # interpreter that actually ran these tests, which in a worktree or a
        # second local venv is not backend/venv. Naming the wrong path sends
        # the reader to inspect a clean environment and discount a true
        # warning.
        terminalreporter.write_line(
            f"{sys.prefix} does not match backend/requirements.txt — these "
            "results describe a tree CI does not run."
        )
        for line in lines:
            terminalreporter.write_line(line)
        terminalreporter.write_line(
            "Fix: pip install -r backend/requirements.txt into that "
            "environment (todo 378)."
        )
    except Exception:  # noqa: BLE001 - includes env_integrity being None
        return
