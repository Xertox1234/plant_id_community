#!/usr/bin/env python3
"""Tests for the backend interpreter lookup in the two staged-file commit hooks.

Run: python3 scripts/test_staged_hooks_venv.py
Also run by .github/workflows/harness-ci.yml.

scripts/test-staged.sh (pytest-staged) and scripts/mypy_staged.py (mypy-staged)
need backend/venv/bin/python. A git worktree has none (backend/venv is
gitignored), so both failed closed in every worktree and agents committed with
SKIP=mypy-staged,pytest-staged (todo 687). They now fall back to the main
checkout's venv, found through `git rev-parse --git-common-dir`, and still fail
closed when neither venv exists.

Each case builds a throwaway repo, copies the two real scripts into it, and
puts a stub `python` where a venv would be. The stub logs its argv and
PYTHONPATH, so a case can tell which interpreter ran and with what.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
TEST_STAGED = HERE / "test-staged.sh"
MYPY_STAGED = HERE / "mypy_staged.py"
BASH = shutil.which("bash") or "bash"

STUB = """#!/bin/sh
printf '%s|%s|%s\\n' "$0" "$*" "${PYTHONPATH:-}" >> "$STUB_LOG"
exit 0
"""

PYPROJECT = """[tool.mypy]
files = ["apps/core"]
"""


def git(*args: str, cwd: pathlib.Path) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


def clean_env(log: pathlib.Path, **extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_") and k != "PYTHONPATH"}
    env["STUB_LOG"] = str(log)
    env.update(extra)
    return env


def make_venv(checkout: pathlib.Path) -> pathlib.Path:
    py = checkout / "backend" / "venv" / "bin" / "python"
    py.parent.mkdir(parents=True)
    py.write_text(STUB)
    py.chmod(0o755)
    return py


class StagedHookVenvTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = pathlib.Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.log = self.tmp / "stub.log"
        self.main = self.tmp / "main"
        (self.main / "scripts").mkdir(parents=True)
        (self.main / "backend").mkdir()
        shutil.copy(TEST_STAGED, self.main / "scripts" / "test-staged.sh")
        shutil.copy(MYPY_STAGED, self.main / "scripts" / "mypy_staged.py")
        (self.main / "backend" / "pyproject.toml").write_text(PYPROJECT)
        (self.main / ".gitignore").write_text("backend/venv/\n")
        git("init", "-q", "-b", "main", cwd=self.main)
        git("add", "-A", cwd=self.main)
        git("commit", "-q", "-m", "init", cwd=self.main)
        self.wt = self.tmp / "main" / ".claude" / "worktrees" / "fresh"
        git("worktree", "add", "-q", "-b", "fresh", str(self.wt), cwd=self.main)

    def run_pytest_hook(self, checkout: pathlib.Path, **env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [BASH, str(checkout / "scripts" / "test-staged.sh"), "backend", "backend/apps/core/tests/test_a.py"],
            cwd=checkout,
            env=clean_env(self.log, **env),
            capture_output=True,
            text=True,
        )

    def run_mypy_hook(self, checkout: pathlib.Path, **env: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(checkout / "scripts" / "mypy_staged.py"), "backend/apps/core/models.py"],
            cwd=checkout,
            env=clean_env(self.log, **env),
            capture_output=True,
            text=True,
        )

    def stub_calls(self) -> list[list[str]]:
        if not self.log.exists():
            return []
        return [line.split("|") for line in self.log.read_text().splitlines()]

    def test_worktree_without_venv_uses_main_checkout_venv(self) -> None:
        main_py = make_venv(self.main)
        self.assertFalse((self.wt / "backend" / "venv").exists())

        pytest_run = self.run_pytest_hook(self.wt)
        mypy_run = self.run_mypy_hook(self.wt)

        self.assertEqual(pytest_run.returncode, 0, pytest_run.stderr)
        self.assertEqual(mypy_run.returncode, 0, mypy_run.stderr)
        calls = self.stub_calls()
        self.assertEqual(len(calls), 2, calls)
        (py1, args1, path1), (py2, args2, path2) = calls
        self.assertEqual(py1, str(main_py))
        self.assertEqual(py2, str(main_py))
        self.assertIn("-m pytest", args1)
        self.assertIn("apps/core/tests/test_a.py", args1)
        self.assertIn("-m mypy", args2)
        self.assertIn("apps/core/models.py", args2)
        # The worktree's own forum package comes first, not the main checkout's.
        forum = str(self.wt / "backend" / "packages" / "wagtail_forum")
        self.assertEqual(path1.split(":")[0], forum)
        self.assertEqual(path2.split(":")[0], forum)
        self.assertFalse((self.wt / "backend" / "venv").exists(), "no symlink was left behind")

    def test_fallback_works_under_a_commit_hook_git_dir(self) -> None:
        # git exports GIT_DIR (the worktree's gitdir) and GIT_INDEX_FILE to hooks.
        main_py = make_venv(self.main)
        gitdir = self.main / ".git" / "worktrees" / "fresh"
        env = {"GIT_DIR": str(gitdir), "GIT_INDEX_FILE": str(gitdir / "index")}

        self.assertEqual(self.run_pytest_hook(self.wt, **env).returncode, 0)
        self.assertEqual(self.run_mypy_hook(self.wt, **env).returncode, 0)
        self.assertEqual([c[0] for c in self.stub_calls()], [str(main_py), str(main_py)])

    def test_own_venv_wins_over_main_checkout_venv(self) -> None:
        make_venv(self.main)
        own_py = make_venv(self.wt)

        self.assertEqual(self.run_pytest_hook(self.wt).returncode, 0)
        self.assertEqual(self.run_mypy_hook(self.wt).returncode, 0)
        calls = self.stub_calls()
        self.assertEqual([c[0] for c in calls], [str(own_py), str(own_py)])
        forum = str(self.wt / "backend" / "packages" / "wagtail_forum")
        self.assertEqual([c[2].split(":")[0] for c in calls], [forum, forum])

    def test_main_checkout_uses_its_own_venv(self) -> None:
        main_py = make_venv(self.main)

        self.assertEqual(self.run_pytest_hook(self.main).returncode, 0)
        self.assertEqual(self.run_mypy_hook(self.main).returncode, 0)
        self.assertEqual([c[0] for c in self.stub_calls()], [str(main_py), str(main_py)])

    def test_no_venv_anywhere_fails_closed(self) -> None:
        pytest_run = self.run_pytest_hook(self.wt)
        mypy_run = self.run_mypy_hook(self.wt)

        self.assertEqual(pytest_run.returncode, 1)
        self.assertEqual(mypy_run.returncode, 1)
        self.assertIn("missing here and in the main checkout", pytest_run.stderr)
        self.assertIn("SKIP=pytest-staged", pytest_run.stderr)
        self.assertIn("missing here and in the main checkout", mypy_run.stderr)
        self.assertIn("SKIP=mypy-staged", mypy_run.stderr)
        self.assertEqual(self.stub_calls(), [])

    def test_no_venv_outside_any_git_repo_fails_closed(self) -> None:
        loose = self.tmp / "loose"
        (loose / "scripts").mkdir(parents=True)
        (loose / "backend").mkdir()
        shutil.copy(TEST_STAGED, loose / "scripts" / "test-staged.sh")
        shutil.copy(MYPY_STAGED, loose / "scripts" / "mypy_staged.py")
        (loose / "backend" / "pyproject.toml").write_text(PYPROJECT)
        env = {"GIT_CEILING_DIRECTORIES": str(self.tmp)}

        pytest_run = self.run_pytest_hook(loose, **env)
        mypy_run = self.run_mypy_hook(loose, **env)

        self.assertEqual(pytest_run.returncode, 1)
        self.assertEqual(mypy_run.returncode, 1)
        self.assertIn("missing here and in the main checkout", pytest_run.stderr)
        self.assertIn("missing here and in the main checkout", mypy_run.stderr)
        self.assertEqual(self.stub_calls(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
