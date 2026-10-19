#!/usr/bin/env python3
"""pre-commit hook body: mypy on the backend Python files staged in this commit.

The CI gate (backend-ci.yml) type-checks the paths listed in
backend/pyproject.toml [tool.mypy] `files`; that list is the single source of
truth for what is gated. This hook runs mypy on the staged files and

  * BLOCKS the commit on any error in a file under a gated path, so the
    CI failure moves to commit time; and
  * prints one advisory line per other file ("N error(s), not gated") so the
    debt in an ungated app is visible while you are in the file, without
    turning 1,000+ pre-existing errors into a wall nobody reads.

Tests are excluded from the gate (owner decision 2026-10-19): the
`apps.*.tests.*` ignore_errors override in pyproject.toml applies to files
named on the command line too, so a staged test file reports nothing here;
the hook's `exclude` in .pre-commit-config.yaml just skips the run for them.

Fail-closed: a missing backend/venv fails the commit with a message rather
than passing by emptiness. Bypass one commit with SKIP=mypy-staged.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
PYTHON = BACKEND / "venv" / "bin" / "python"
ERROR_LINE = re.compile(r"^(?P<path>[^:\n]+\.py):\d+:(?:\d+:)? error: ")


def gated_prefixes() -> list[str]:
    with open(BACKEND / "pyproject.toml", "rb") as fh:
        cfg = tomllib.load(fh)
    files = cfg.get("tool", {}).get("mypy", {}).get("files", [])
    if isinstance(files, str):
        files = [part.strip() for part in files.split(",") if part.strip()]
    return [str(pathlib.PurePosixPath(p)).rstrip("/") + "/" for p in files]


def is_gated(path: str, prefixes: list[str]) -> bool:
    return any(path == prefix.rstrip("/") or path.startswith(prefix) for prefix in prefixes)


def main(argv: list[str]) -> int:
    staged = [a[len("backend/") :] for a in argv if a.startswith("backend/") and a.endswith(".py")]
    if not staged:
        return 0
    if not PYTHON.is_file():
        print(
            "mypy-staged: backend/venv/bin/python is missing; create the venv "
            "(see backend/CLAUDE.md) or commit with SKIP=mypy-staged",
            file=sys.stderr,
        )
        return 1
    prefixes = gated_prefixes()
    if not prefixes:
        print("mypy-staged: [tool.mypy] files is empty in backend/pyproject.toml; nothing is gated", file=sys.stderr)
        return 1

    proc = subprocess.run(
        [str(PYTHON), "-m", "mypy", "--no-error-summary", "--no-pretty", *staged],
        cwd=BACKEND,
        capture_output=True,
        text=True,
    )
    if proc.returncode not in (0, 1):
        # 2 = mypy itself failed (bad config, crash): never pass by emptiness.
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        print(f"mypy-staged: mypy exited {proc.returncode}", file=sys.stderr)
        return proc.returncode

    blocking: list[str] = []
    advisory: dict[str, int] = {}
    for line in proc.stdout.splitlines():
        m = ERROR_LINE.match(line)
        if not m:
            continue
        path = m.group("path")
        if is_gated(path, prefixes):
            blocking.append(line)
        else:
            advisory[path] = advisory.get(path, 0) + 1

    for path, count in sorted(advisory.items()):
        print(f"mypy-staged: {count} error(s) in {path} (advisory: not under a gated path, see [tool.mypy] files)")
    if blocking:
        print("\n".join(blocking))
        print(
            f"mypy-staged: {len(blocking)} error(s) in gated file(s) "
            f"({', '.join(p.rstrip('/') for p in prefixes)}); fix them or commit with SKIP=mypy-staged",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
