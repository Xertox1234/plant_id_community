#!/usr/bin/env python3
"""Find, and with --apply delete, orphaned build output on the U34Bolt drive.

A worktree's native build output is redirected to the shared SSD by a symlink,
``plant_community_mobile/build -> /Volumes/U34Bolt/plant_id_community/build/<name>``.
``git worktree remove`` deletes only the link, so the folder it pointed at stays
behind. This script lists every entry of that build root, compares it against
the ``build`` link of every live worktree (``git worktree list --porcelain``),
and reports each entry no live worktree uses, with its size and last-modified
time (todo 697).

    python3 scripts/clean_build_output.py                 # dry run: report only
    python3 scripts/clean_build_output.py --apply         # delete orphans older than --min-age
    python3 scripts/clean_build_output.py --tmp           # also report old entries in tmp/

Safety rules:
  - Dry run by default; nothing is deleted without ``--apply``.
  - With the drive unmounted (the README's ``df -P`` check, never a bare
    directory test) or a missing root, it prints why and exits 0.
  - Only direct children of the build root are deleted, and only when no live
    worktree's ``build`` link resolves to, into, or above them.
  - Symlinks are never followed: a link at the top level is unlinked, and
    ``shutil.rmtree`` removes a link inside an orphan as a link.
  - The last-modified time is the newest mtime anywhere in the entry, so a
    build still writing deep inside a folder keeps it young.
  - If the worktree list cannot be read, nothing is deleted.
  - ``--tmp`` only reports: logs and APKs in tmp/ are often kept on purpose.

Run its tests: python3 scripts/test_clean_build_output.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

MOUNT = "/Volumes/U34Bolt"
DEFAULT_ROOT = f"{MOUNT}/plant_id_community/build"
DEFAULT_TMP_ROOT = f"{MOUNT}/plant_id_community/tmp"
BUILD_LINK = "plant_community_mobile/build"
DEFAULT_MIN_AGE_DAYS = 2.0
TMP_REPORT_AGE_DAYS = 14.0


@dataclass
class Entry:
    path: Path
    size: int
    mtime: float
    live_for: list[str]
    unreadable: str | None = None  # set when measure() failed: never deleted

    @property
    def name(self) -> str:
        return self.path.name


def is_mounted(mount: str) -> bool:
    """True when ``mount`` is itself a mount point, per ``df -P``."""
    try:
        out = subprocess.run(
            ["df", "-P", mount], capture_output=True, text=True, check=False
        ).stdout
    except OSError:
        return False
    lines = out.strip().splitlines()
    if len(lines) < 2:
        return False
    fields = lines[1].split()
    return bool(fields) and fields[-1] == mount


def git_worktrees(repo: str) -> list[str]:
    """Paths of every worktree git knows about. Raises on failure."""
    out = subprocess.run(
        ["git", "-C", repo, "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [line[len("worktree ") :] for line in out.splitlines() if line.startswith("worktree ")]


def live_targets(worktrees: list[str]) -> dict[str, str]:
    """Map the resolved target of each worktree's ``build`` link to that worktree."""
    targets: dict[str, str] = {}
    for wt in worktrees:
        link = os.path.join(wt, BUILD_LINK)
        if os.path.lexists(link):
            targets[os.path.realpath(link)] = wt
    return targets


def _related(a: str, b: str) -> bool:
    """True when ``a`` and ``b`` are the same path or one contains the other.

    Compared case-insensitively: U34Bolt is case-insensitive APFS, and
    ``realpath`` does not correct a link's letter case, so ``build/G1`` and
    ``build/g1`` are one folder. Folding can only make more entries live.
    """
    a, b = a.casefold(), b.casefold()
    return a == b or a.startswith(b + os.sep) or b.startswith(a + os.sep)


def measure(path: Path) -> tuple[int, float]:
    """Total size and newest mtime under ``path``, never following a symlink.

    Raises OSError when the entry, or any folder inside it, cannot be read:
    its newest mtime is then unknown, so it must not be judged old.
    """
    st = os.lstat(path)
    size, newest = st.st_size, st.st_mtime
    if path.is_symlink() or not path.is_dir():
        return size, newest

    def fail(exc: OSError) -> None:
        raise exc

    for dirpath, dirnames, filenames in os.walk(path, followlinks=False, onerror=fail):
        for name in dirnames + filenames:
            s = os.lstat(os.path.join(dirpath, name))
            size += s.st_size
            newest = max(newest, s.st_mtime)
    return size, newest


def scan(root: Path, targets: dict[str, str]) -> list[Entry]:
    entries = []
    real_root = os.path.realpath(root)
    for child in sorted(root.iterdir()):
        try:
            size, mtime = measure(child)
            unreadable = None
        except OSError as exc:
            size, mtime, unreadable = 0, 0.0, str(exc)
        # A top-level link is judged by where it points AND by its own path
        # (the parent resolved, the link itself not).
        resolved = {os.path.realpath(child), os.path.join(real_root, child.name)}
        live = sorted(
            {wt for t, wt in targets.items() for r in resolved if _related(r, t)}
        )
        entries.append(Entry(child, size, mtime, live, unreadable))
    return entries


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"  # unreachable; keeps type checkers happy


def stamp(mtime: float) -> str:
    return dt.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")


def delete(root: Path, entry: Path) -> None:
    """Delete one direct child of ``root`` without following any symlink."""
    if os.path.dirname(os.path.abspath(entry)) != os.path.abspath(root):
        raise ValueError(f"refusing to delete {entry}: not a direct child of {root}")
    if entry.is_symlink() or not entry.is_dir():
        os.unlink(entry)
        return
    if os.path.dirname(os.path.realpath(entry)) != os.path.realpath(root):
        raise ValueError(f"refusing to delete {entry}: resolves outside {root}")
    shutil.rmtree(entry)


def report_tmp(tmp_root: Path, now: float, out) -> None:
    if not tmp_root.is_dir():
        print(f"tmp: {tmp_root} does not exist; nothing to report.", file=out)
        return
    cutoff = now - TMP_REPORT_AGE_DAYS * 86400
    old = []
    for child in sorted(tmp_root.iterdir()):
        try:
            size, mtime = measure(child)
        except OSError:
            continue  # report only: an unreadable entry is simply not listed
        if mtime < cutoff:
            old.append((child, size, mtime))
    for child, size, mtime in old:
        print(f"tmp-old {human(size)} {stamp(mtime)} {child.name}", file=out)
    total = sum(s for _, s, _ in old)
    print(
        f"tmp: {len(old)} entries older than {TMP_REPORT_AGE_DAYS:g} days, "
        f"{human(total)}. Report only: nothing in tmp/ is ever deleted.",
        file=out,
    )


def main(
    argv: list[str] | None = None,
    *,
    worktrees: list[str] | None = None,
    now: float | None = None,
    out=None,
) -> int:
    out = out or sys.stdout
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--root", default=DEFAULT_ROOT, help=f"build root (default {DEFAULT_ROOT})")
    p.add_argument(
        "--mount",
        default=None,
        help=f"mount point that must be mounted first (default {MOUNT} when --root is the default)",
    )
    p.add_argument("--apply", action="store_true", help="delete orphans older than --min-age")
    p.add_argument(
        "--min-age",
        type=float,
        default=DEFAULT_MIN_AGE_DAYS,
        metavar="DAYS",
        help=f"only delete orphans last written more than DAYS ago (default {DEFAULT_MIN_AGE_DAYS:g})",
    )
    p.add_argument(
        "--tmp", action="store_true", help="also report (never delete) old entries in tmp/"
    )
    p.add_argument("--tmp-root", default=DEFAULT_TMP_ROOT, help=argparse.SUPPRESS)
    p.add_argument(
        "--repo",
        default=str(Path(__file__).resolve().parent.parent),
        help="any checkout of the repo (default: this script's)",
    )
    args = p.parse_args(argv)
    now = time.time() if now is None else now

    # Any root on the drive checks the mount, however it is spelled: with the
    # drive gone, /Volumes/U34Bolt/... could be a stray folder on the system disk.
    under_mount = os.path.abspath(args.root).casefold().startswith(MOUNT.casefold() + os.sep)
    mount = args.mount or (MOUNT if under_mount else None)
    if mount and not is_mounted(mount):
        print(f"{mount} is not mounted; nothing to do.", file=out)
        return 0
    root = Path(args.root)
    if not root.is_dir():
        print(f"{root} does not exist; nothing to do.", file=out)
        return 0

    try:
        wts = git_worktrees(args.repo) if worktrees is None else worktrees
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"cannot list worktrees ({exc}); nothing deleted.", file=sys.stderr)
        return 1
    targets = live_targets(wts)

    entries = scan(root, targets)
    orphans = [e for e in entries if not e.live_for and not e.unreadable]
    for e in entries:
        if e.unreadable and not e.live_for:
            print(f"skip   {e.name}: unreadable, never deleted ({e.unreadable})", file=out)
        elif e.live_for:
            print(f"live   {human(e.size)} {stamp(e.mtime)} {e.name} <- {', '.join(e.live_for)}", file=out)
        else:
            print(f"orphan {human(e.size)} {stamp(e.mtime)} {e.name}", file=out)
    print(f"Orphans: {len(orphans)}, {human(sum(e.size for e in orphans))}.", file=out)

    status = 0
    if not args.apply:
        print("Dry run: nothing deleted.", file=out)
    else:
        cutoff = now - args.min_age * 86400
        freed = deleted = 0
        for e in orphans:
            if e.mtime > cutoff:
                print(f"kept   {e.name}: written within {args.min_age:g} days", file=out)
                continue
            try:
                delete(root, e.path)
            except (OSError, ValueError) as exc:
                print(f"failed {e.name}: {exc}", file=sys.stderr)
                status = 1
                continue
            deleted += 1
            freed += e.size
            print(f"deleted {e.name}", file=out)
        print(f"Deleted: {deleted}, {human(freed)} freed.", file=out)

    if args.tmp:
        report_tmp(Path(args.tmp_root), now, out)
    return status


if __name__ == "__main__":
    sys.exit(main())
