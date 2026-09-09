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

Everything here fails open. A broken environment check must never break a test
run — that would be strictly worse than the problem it reports.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

# Loaded by file path rather than by adding apps/core to sys.path. That shim
# would make every module beside it importable as a top-level name — `admin`,
# `models`, `views`, `security`, `exceptions`, `validators`, `middleware` — in
# every test run, shadowing any third-party package of the same name. Tests
# reach this exact module object via `from conftest import env_integrity`, so
# monkeypatching in a test affects the code these hooks call.
_spec = importlib.util.spec_from_file_location(
    "_env_integrity", Path(__file__).parent / "apps" / "core" / "env_integrity.py"
)
env_integrity = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(env_integrity)


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=Path(__file__).parent,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _tree_state() -> str:
    head = _git("rev-parse", "--short", "HEAD") or "unknown"
    status = _git("status", "--porcelain")
    dirty = len([line for line in status.splitlines() if line.strip()])
    return f"HEAD {head}, {dirty} uncommitted file(s)"


def pytest_report_header(config):
    """Unconditional environment stamp. Never raises."""
    try:
        pins = env_integrity.read_pins()
        installed = env_integrity.installed_versions()
        editable = env_integrity.editable_names()
        mismatched, missing, extra = env_integrity.compare(pins, installed, editable)
        deps = (
            f"{len(pins)} pinned, {len(mismatched)} mismatched, "
            f"{len(missing)} not installed, {len(extra)} unpinned"
        )
        return [
            f"env: {sys.prefix}",
            f"tree: {_tree_state()}",
            f"deps: {deps}",
        ]
    except Exception:  # noqa: BLE001 - a stamp must never break a run
        return []


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Name the drifted packages, adjacent to the pass/fail counts."""
    try:
        lines = env_integrity.drift_report()
    except Exception:  # noqa: BLE001
        return
    if not lines:
        return
    terminalreporter.write_sep("=", "ENVIRONMENT DRIFT", red=True, bold=True)
    terminalreporter.write_line(
        "backend/venv does not match backend/requirements.txt — these results "
        "describe a tree CI does not run."
    )
    for line in lines:
        terminalreporter.write_line(line)
    terminalreporter.write_line(
        "Fix: pip install -r backend/requirements.txt (todo 378)."
    )
