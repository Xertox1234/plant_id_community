#!/usr/bin/env python3
"""Tests for scripts/check_flutter_codegen.py (the Flutter codegen pre-commit hook).

Run: python3 scripts/test_check_flutter_codegen.py
Also run by .github/workflows/harness-ci.yml.

build_runner itself is stubbed: these tests pin which commits the hook builds
for, and how it reads a regeneration that changed or added a generated file.
"""

from __future__ import annotations

import io
import pathlib
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import check_flutter_codegen as cfc  # noqa: E402

PROVIDER = """import 'package:riverpod_annotation/riverpod_annotation.dart';

part 'user_profile_service.g.dart';

@riverpod
class UserProfileService extends _$UserProfileService {}
"""
PLAIN = "class Plain {}\n"


class Repo:
    """A throwaway git repo holding a fake plant_community_mobile tree."""

    def __init__(self, tmp: str):
        self.root = pathlib.Path(tmp)
        self.lib = self.root / cfc.MOBILE / "lib"
        self.lib.mkdir(parents=True)
        (self.root / cfc.MOBILE / ".dart_tool").mkdir()
        for args in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
            self.git(*args)

    def git(self, *args: str) -> None:
        subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)

    def write(self, rel: str, text: str) -> str:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return rel

    def commit_all(self) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "x")


def stub_build(effect=None, returncode=0):
    """A build_runner stand-in: calls ``effect(mobile)`` and records each call."""
    calls = []

    def build(mobile):
        calls.append(mobile)
        if effect:
            effect(mobile)
        return subprocess.CompletedProcess([], returncode, "built", "")

    build.calls = calls
    return build


def run(repo: Repo, paths: list[str], build) -> tuple[int, str]:
    out = io.StringIO()
    with redirect_stdout(out):
        code = cfc.main(paths, root=repo.root, build=build)
    return code, out.getvalue()


class CodegenSourcesTests(unittest.TestCase):
    def test_only_a_file_with_a_g_dart_part_is_a_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            provider = repo.write(f"{cfc.MOBILE}/lib/a.dart", PROVIDER)
            plain = repo.write(f"{cfc.MOBILE}/lib/b.dart", PLAIN)
            generated = repo.write(f"{cfc.MOBILE}/lib/a.g.dart", "part of 'a.dart';\n")
            dq = repo.write(f"{cfc.MOBILE}/lib/c.dart", 'part "c.g.dart";\n')
            freezed = repo.write(f"{cfc.MOBILE}/lib/d.dart", "part 'd.freezed.dart';\n")
            self.assertEqual(
                cfc.codegen_sources(
                    [provider, plain, generated, dq, freezed, "README.md"], repo.root
                ),
                [provider, dq, freezed],
            )

    def test_a_part_in_a_comment_line_is_not_matched_mid_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            rel = repo.write(f"{cfc.MOBILE}/lib/a.dart", "// see part 'x.g.dart';\n")
            self.assertEqual(cfc.codegen_sources([rel], repo.root), [])


class MainTests(unittest.TestCase):
    def test_a_commit_without_a_codegen_source_never_builds(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            rel = repo.write(f"{cfc.MOBILE}/lib/b.dart", PLAIN)
            build = stub_build()
            self.assertEqual(run(repo, [rel], build)[0], 0)
            self.assertEqual(build.calls, [])

    def test_current_generated_code_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            rel = repo.write(f"{cfc.MOBILE}/lib/a.dart", PROVIDER)
            repo.write(f"{cfc.MOBILE}/lib/a.g.dart", "hash-1\n")
            repo.commit_all()
            build = stub_build()  # regenerates the same content
            self.assertEqual(run(repo, [rel], build)[0], 0)
            self.assertEqual(len(build.calls), 1)

    def test_a_stale_generated_file_fails_and_names_it(self):
        """Todo 651: a source edit changed the embedded hash, nothing else."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            rel = repo.write(f"{cfc.MOBILE}/lib/a.dart", PROVIDER)
            repo.write(f"{cfc.MOBILE}/lib/a.g.dart", "hash-1\n")
            repo.commit_all()
            build = stub_build(lambda m: (m / "lib" / "a.g.dart").write_text("hash-2\n"))
            code, out = run(repo, [rel], build)
            self.assertEqual(code, 1)
            self.assertIn(f"{cfc.MOBILE}/lib/a.g.dart", out)

    def test_a_new_untracked_generated_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            rel = repo.write(f"{cfc.MOBILE}/lib/new.dart", PROVIDER)
            build = stub_build(lambda m: (m / "lib" / "new.g.dart").write_text("x\n"))
            code, out = run(repo, [rel], build)
            self.assertEqual(code, 1)
            self.assertIn(f"{cfc.MOBILE}/lib/new.g.dart", out)

    def test_a_failed_build_fails_with_its_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            rel = repo.write(f"{cfc.MOBILE}/lib/a.dart", PROVIDER)
            code, out = run(repo, [rel], stub_build(returncode=1))
            self.assertEqual(code, 1)
            self.assertIn("build_runner failed", out)

    def test_a_worktree_without_dart_tool_says_to_run_pub_get(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Repo(tmp)
            (repo.root / cfc.MOBILE / ".dart_tool").rmdir()
            rel = repo.write(f"{cfc.MOBILE}/lib/a.dart", PROVIDER)
            build = stub_build()
            code, out = run(repo, [rel], build)
            self.assertEqual(code, 1)
            self.assertIn("flutter pub get", out)
            self.assertEqual(build.calls, [])


class RunBuildEnvTest(unittest.TestCase):
    def test_the_build_never_sees_git_hook_variables(self):
        # In a worktree commit git exports GIT_DIR to hooks. Flutter reads its
        # own SDK version with git, so with GIT_DIR set it read this repo,
        # reported 0.0.0-unknown and pub refused to resolve (2026-10-19).
        hook_env = {
            "PATH": "/usr/bin",
            "GIT_DIR": "/repo/.git/worktrees/x",
            "GIT_INDEX_FILE": "/repo/.git/worktrees/x/index",
            "GIT_WORK_TREE": "/repo",
            "GIT_PREFIX": "",
        }
        with mock.patch.dict(cfc.os.environ, hook_env, clear=True), mock.patch.object(
            cfc.subprocess, "run"
        ) as run_:
            cfc.run_build(pathlib.Path("/repo/plant_community_mobile"))
        env = run_.call_args.kwargs["env"]
        self.assertEqual(env["PATH"], "/usr/bin")
        for name in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "GIT_PREFIX"):
            self.assertNotIn(name, env)


if __name__ == "__main__":
    unittest.main()
