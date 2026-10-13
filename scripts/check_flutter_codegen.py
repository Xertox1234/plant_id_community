#!/usr/bin/env python3
"""Pre-commit: regenerate Flutter codegen when a staged codegen source changed.

Riverpod embeds a hash of each provider's own source (the annotated class or
function) in its ``.g.dart`` (``_$fooHash``), so any edit inside a provider --
a comment, a log line, an argument to a thrown exception -- makes the generated
file stale. ``flutter analyze``, ``flutter test`` and the app all pass with the
stale file; only mobile CI's "Ensure generated code is committed" step
(``build_runner`` + ``git diff --exit-code``) caught it, after the push (todo
651, PR #1127: one new argument in ``updateProfile``).

It is cheaper to rebuild than to decide whether an edit touched a provider, so
the hook rebuilds whenever such a file is staged; an edit outside every
provider regenerates nothing and passes.

This hook runs the same ``build_runner`` CI runs, but only when a staged file
under ``plant_community_mobile/lib`` declares a ``part '....g.dart';``, so an
ordinary Dart commit pays nothing. When regeneration changes a generated file
it fails and leaves the regenerated file in the tree, like Black: stage it and
commit again.

Usage (pre-commit passes the staged paths): check_flutter_codegen.py PATH...
"""

from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import sys

MOBILE = "plant_community_mobile"
# A source whose generated half build_runner writes: `part 'foo.g.dart';`.
PART_G_DART = re.compile(r"""^\s*part\s+['"][^'"]+\.g\.dart['"]\s*;""", re.MULTILINE)
GENERATED = re.compile(r"\.(g|freezed)\.dart$")
BUILD = ["dart", "run", "build_runner", "build", "--delete-conflicting-outputs"]


def codegen_sources(paths: list[str], root: pathlib.Path) -> list[str]:
    """The staged hand-written Dart files that have a generated half."""
    found = []
    for rel in paths:
        if not rel.endswith(".dart") or GENERATED.search(rel):
            continue
        path = root / rel
        if path.is_file() and PART_G_DART.search(path.read_text(errors="ignore")):
            found.append(rel)
    return found


def changed_generated(root: pathlib.Path) -> list[str]:
    """Generated files that differ from the index, or are new and untracked."""

    def git(*args: str) -> list[str]:
        out = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, check=True
        ).stdout
        return [line for line in out.splitlines() if GENERATED.search(line)]

    scope = [f"{MOBILE}/lib", f"{MOBILE}/test"]
    modified = git("diff", "--name-only", "--", *scope)
    untracked = git("ls-files", "--others", "--exclude-standard", "--", *scope)
    return sorted(set(modified) | set(untracked))


def run_build(mobile: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(BUILD, cwd=mobile, capture_output=True, text=True)


def main(argv: list[str], root: pathlib.Path | None = None, build=run_build) -> int:
    root = root or pathlib.Path.cwd()
    sources = codegen_sources(argv, root)
    if not sources:
        return 0
    mobile = root / MOBILE
    if build is run_build and shutil.which("dart") is None:
        print("[FLUTTER_CODEGEN] dart is not on PATH: cannot check generated code")
        return 1
    if not (mobile / ".dart_tool").is_dir():
        print(
            f"[FLUTTER_CODEGEN] {MOBILE}/.dart_tool is missing: run "
            f"`flutter pub get` in {MOBILE} first (a fresh worktree has none)"
        )
        return 1
    result = build(mobile)
    if result.returncode != 0:
        print("[FLUTTER_CODEGEN] build_runner failed:")
        print("\n".join((result.stdout + result.stderr).splitlines()[-20:]))
        return 1
    stale = changed_generated(root)
    if stale:
        print(
            "[FLUTTER_CODEGEN] generated code was stale for "
            + ", ".join(sources)
            + ". Regenerated (stage these and commit again):"
        )
        for path in stale:
            print(f"  {path}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
