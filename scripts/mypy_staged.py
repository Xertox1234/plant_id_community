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

The interpreter is this checkout's backend/venv, or, in a git worktree (which
has no venv: it is gitignored), the main checkout's backend/venv (todo 687).
scripts/test-staged.sh resolves it the same way.

Fail-closed: no venv in either place fails the commit with a message rather
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
VENV_PYTHON = pathlib.Path("backend") / "venv" / "bin" / "python"
ERROR_LINE = re.compile(r"^(?P<path>[^:\n]+\.py):\d+:(?:\d+:)? error: ")


def main_checkout() -> pathlib.Path | None:
    """The main worktree of this repo: the parent of `git rev-parse --git-common-dir`."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    return pathlib.Path(proc.stdout.strip()).parent


def resolve_backend_python() -> pathlib.Path | None:
    """This checkout's backend/venv python, else the main checkout's, else None.

    Never resolve() the result: a venv's bin/python is a symlink, and the venv
    is found from the path it is invoked by.
    """
    own = ROOT / VENV_PYTHON
    if own.is_file():
        return own
    main = main_checkout()
    if main is not None:
        shared = main / VENV_PYTHON
        if shared.is_file():
            return shared
    return None


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
    python = resolve_backend_python()
    if python is None:
        print(
            "mypy-staged: backend/venv/bin/python is missing here and in the main checkout; "
            "create the venv (see backend/CLAUDE.md) or commit with SKIP=mypy-staged",
            file=sys.stderr,
        )
        return 1
    prefixes = gated_prefixes()
    if not prefixes:
        print("mypy-staged: [tool.mypy] files is empty in backend/pyproject.toml; nothing is gated", file=sys.stderr)
        return 1

    proc = subprocess.run(
        [str(python), "-m", "mypy", "--no-error-summary", "--no-pretty", *staged],
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
