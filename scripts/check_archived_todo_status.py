#!/usr/bin/env python3
"""Fail when an archived todo's frontmatter does not say the work is finished.

Why this exists: `todos/TEMPLATE.md:10` already states the rule -- *"The
filename status segment MUST match the frontmatter status value."* Nothing
enforced it, so a todo could be moved into `archive/` with every acceptance
criterion unchecked and a filename that claimed otherwise. That is not
hypothetical bookkeeping:

  - `todos/archive/005-completed-p1-api-key-rotation-verification.md` existed to
    confirm an API key had been rotated after the 2025-10-23 incident. Filename
    `completed`, frontmatter `status: ready`, 7 unchecked ACs, rotation date left
    as the literal template `[DATE]`. On 2026-09-13, eleven months later, a
    PlantNet key from that same incident was found **still live** in the public
    repo -- `GET my-api.plantnet.org/v2/projects` returned HTTP 200 and 77
    projects. One request found what the archived checkbox had asserted was done.
  - `backend/todos/archive/2025-11-01-003-resolved-p1-env-example-secret-placeholders.md`
    -- `status: pending`, 6 unchecked ACs, archived as "resolved". Ten months
    later todo 367 rediscovered the same problem, by which point
    `JWT_SECRET_KEY`'s 66-character *placeholder* was accepted in production and
    signing every JWT.

Both share one shape: the deliverable was an **external verification**, so it
left no artifact in the repo. The unchecked box was the only record, and moving
the file into `archive/` silently converted "nobody did this" into "done".

WHAT IS CHECKED (two rules, both on the same status vocabulary)

  ARCHIVED_OPEN      A todo under an `archive/` directory whose frontmatter
                     status is in the `open` class. This is the load-bearing
                     rule. It is deliberately broader than the filename-vs-
                     frontmatter comparison todo 390 proposed, because that
                     narrower reading has a hole the exact size of the failure
                     mode: `todos/archive/017-pending-p2-registration-csrf-
                     bypass.md` (a CSRF bypass) and `018-pending-p2-jwt-token-
                     lifetime.md` are *honest* -- filename and frontmatter both
                     say `pending` -- and archived unfinished anyway. A mismatch
                     rule waves those through for being consistently wrong.

  FILENAME_OVERCLAIM The filename's status class and the frontmatter's status
                     class disagree. Compared by CLASS, not by string: 24 of the
                     50 literal string mismatches in this repo are
                     `completed`-vs-`resolved` synonym noise, and failing on
                     those would bury the one real hit.

STATUS VOCABULARY  (every value observed in this repo, mapped to a class)

  done        completed, complete, resolved, done, fixed
              The work landed.
  dropped     closed, skipped, superseded
              Terminal, but the work was deliberately NOT done. Distinct from
              `done` on purpose: `todos/archive/013-completed-p2-threadpool-
              overengineering.md` carries `status: closed` + `resolution:
              wont-fix` under a filename claiming `completed`. That is the only
              FILENAME_OVERCLAIM hit, and collapsing the two classes would hide
              it.
  open        pending, ready, in_progress, blocked
              Not finished. Illegal under `archive/`.

  A status outside this table is reported as UNKNOWN_STATUS rather than guessed
  at, so adding a new status word to the project is a deliberate edit here.

WHAT IS SKIPPED, AND THE LIMITATION THAT CREATES

  A file with no `---` frontmatter block at all is skipped as not-a-todo. Four
  files hit this: two are archive summaries (`ARCHIVE_SUMMARY.md`,
  `2025-11-05-critical-issues-113-116.md`) which genuinely are not todos, but
  two ARE old prose-style todos predating the frontmatter convention
  (`backend/todos/archive/007-completed-jwt-secret-key-enforcement.md`,
  `backend/github-issues/archive/002-completed-security-fix-secret-key-
  default.md`). They state `**Status**: RESOLVED` in prose. This checker cannot
  judge them and does not pretend to -- it governs the frontmatter convention,
  and a file predating that convention is outside its reach. Run with
  `--list-skipped` to see them. A file WITH a frontmatter block but no `status:`
  key is a violation, not a skip.

  Template/index files (TEMPLATE.md, README.md and friends) are skipped by name.

THE ALLOWLIST IS NOT A MUTE BUTTON

  `todos/archive-status-allowlist.yml` carries one entry per grandfathered file
  with a `kind`, a `reason` and a `date`. A stale entry -- one whose file no
  longer violates, or no longer exists -- FAILS the check. Without that, an
  allowlist silently becomes permanent, which is the same decay that let the
  suppression list in `.github/security-suppressions.yml` hide 19 advisories for
  two months. Entries are classed `verified-implemented` (evidence recorded, the
  frontmatter is what is wrong) or `not-triaged` (nobody has confirmed the work
  landed) so the second bucket stays findable and shrinkable.
"""

import argparse
import os
import re
import sys
from collections import Counter

CLASS_OF_STATUS = {
    "completed": "done",
    "complete": "done",
    "resolved": "done",
    "done": "done",
    "fixed": "done",
    "closed": "dropped",
    "skipped": "dropped",
    "superseded": "dropped",
    "pending": "open",
    "ready": "open",
    "in_progress": "open",
    "blocked": "open",
}

# Not todos: templates and index documents that live alongside them.
SKIP_NAMES = {
    "TEMPLATE.md",
    "README.md",
    "GITHUB.md",
    "IMPLEMENTATION.md",
    "QUICK_REFERENCE.md",
    "RESEARCH.md",
    "ARCHIVE_SUMMARY.md",
}

# `042-completed-p1-slug.md` and `2025-11-01-003-resolved-p1-slug.md` both parse.
FILENAME_RE = re.compile(r"^(?:\d{4}-\d{2}-\d{2}-)?\d+-([a-z_]+)-")
STATUS_RE = re.compile(r"^status:\s*(.+?)\s*$", re.M)

DEFAULT_ROOTS = ("todos", "backend/todos", "backend/github-issues")
ALLOWLIST_PATH = "todos/archive-status-allowlist.yml"


def parse(path):
    """Return (frontmatter_status, filename_status, has_frontmatter)."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    if not text.startswith("---\n"):
        return None, None, False
    end = text.find("\n---", 4)
    block = text[4:end] if end != -1 else text
    found = STATUS_RE.search(block)
    status = found.group(1).strip().lower() if found else None
    name_match = FILENAME_RE.match(os.path.basename(path))
    return status, (name_match.group(1).lower() if name_match else None), True


SEVERITY = ("ARCHIVED_OPEN", "MISSING_STATUS", "UNKNOWN_STATUS", "FILENAME_OVERCLAIM")


def scan(roots):
    """Yield one (path, kind, detail) per violating FILE, plus skipped files.

    A file can break both rules at once -- 26 of this repo's 29 do -- so the most
    serious finding wins and the count stays a count of files. That keeps the
    allowlist 1:1 with paths; an allowlist keyed on (path, rule) would let a file
    be excused for being archived-while-open and still fail on the filename, which
    reads as a bug rather than as the ratchet it is meant to be.
    """
    violations, skipped = [], []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirnames, filenames in os.walk(root):
            for name in sorted(filenames):
                if not name.endswith(".md") or name in SKIP_NAMES:
                    continue
                path = os.path.join(dirpath, name)
                status, filename_status, has_fm = parse(path)
                if not has_fm:
                    skipped.append(path)
                    continue
                archived = f"{os.sep}archive{os.sep}" in f"{path}{os.sep}"
                found = []
                if status is None:
                    found.append(("MISSING_STATUS", "frontmatter block has no status: key"))
                else:
                    status_class = CLASS_OF_STATUS.get(status)
                    if status_class is None:
                        found.append(
                            ("UNKNOWN_STATUS", f"status: {status!r} is not in the vocabulary")
                        )
                    else:
                        if archived and status_class == "open":
                            found.append(
                                ("ARCHIVED_OPEN", f"archived while status: {status}")
                            )
                        name_class = CLASS_OF_STATUS.get(filename_status)
                        if filename_status and name_class and name_class != status_class:
                            found.append(
                                (
                                    "FILENAME_OVERCLAIM",
                                    f"filename says {filename_status} ({name_class}), "
                                    f"frontmatter says {status} ({status_class})",
                                )
                            )
                if found:
                    found.sort(key=lambda f: SEVERITY.index(f[0]))
                    kind, detail = found[0]
                    extra = (
                        f" (+ also {', '.join(k for k, _ in found[1:])})" if len(found) > 1 else ""
                    )
                    violations.append((path, kind, detail + extra))
    return violations, skipped


def load_allowlist(path):
    """Return {relpath: entry}. Absent file is an empty allowlist, not an error."""
    if not os.path.exists(path):
        return {}
    try:
        import yaml
    except ImportError:
        print(
            f"error: {path} exists but PyYAML is not installed; "
            "install it or the allowlist cannot be honoured",
            file=sys.stderr,
        )
        raise SystemExit(2)
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    entries = data.get("allow", []) or []
    out = {}
    for entry in entries:
        missing = [k for k in ("path", "kind", "reason", "date") if not entry.get(k)]
        if missing:
            print(
                f"error: {path}: entry {entry.get('path', '<no path>')!r} "
                f"is missing {', '.join(missing)}",
                file=sys.stderr,
            )
            raise SystemExit(2)
        out[entry["path"]] = entry
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--root",
        action="append",
        dest="roots",
        metavar="DIR",
        help=f"directory to scan (repeatable; default: {', '.join(DEFAULT_ROOTS)})",
    )
    parser.add_argument(
        "--allowlist",
        default=ALLOWLIST_PATH,
        help=f"grandfathered-file list (default: {ALLOWLIST_PATH})",
    )
    parser.add_argument(
        "--no-allowlist",
        action="store_true",
        help="ignore the allowlist and report every violation (shows the real backlog)",
    )
    parser.add_argument("--list", action="store_true", help="list every violation")
    parser.add_argument(
        "--list-skipped",
        action="store_true",
        help="list files skipped for having no frontmatter block",
    )
    parser.add_argument(
        "--fail-over",
        type=int,
        metavar="N",
        help="exit 1 if the unallowed violation count exceeds N (0 requires a clean tree)",
    )
    args = parser.parse_args()

    roots = args.roots or list(DEFAULT_ROOTS)
    violations, skipped = scan(roots)

    allow = {} if args.no_allowlist else load_allowlist(args.allowlist)
    violating_paths = {p for p, _kind, _detail in violations}

    # A stale entry fails. An allowlist nobody can be wrong about is an
    # allowlist nobody ever removes from.
    stale = []
    for path, entry in allow.items():
        if not os.path.exists(path):
            stale.append((path, "file no longer exists", entry))
        elif path not in violating_paths:
            stale.append((path, "file no longer violates", entry))

    remaining = [v for v in violations if v[0] not in allow]

    by_kind = Counter(kind for _p, kind, _d in violations)
    by_kind_remaining = Counter(kind for _p, kind, _d in remaining)
    width = max((len(k) for k in by_kind), default=18)
    print(f"{'violation'.ljust(width)}  total  unallowed")
    for kind in sorted(by_kind):
        print(f"{kind.ljust(width)}  {by_kind[kind]:5d}  {by_kind_remaining[kind]:9d}")
    print(f"{'TOTAL'.ljust(width)}  {len(violations):5d}  {len(remaining):9d}")

    allowed_kinds = Counter(e["kind"] for e in allow.values())
    if allow:
        print(
            f"\n{len(allow)} allowlisted "
            f"({', '.join(f'{v} {k}' for k, v in sorted(allowed_kinds.items()))})"
        )
    if skipped:
        print(f"{len(skipped)} file(s) skipped: no frontmatter block, cannot be judged")

    if args.list:
        print()
        for path, kind, detail in sorted(remaining):
            print(f"{path}\n    {kind}: {detail}")
    if args.list_skipped:
        print()
        for path in sorted(skipped):
            print(f"SKIPPED  {path}")

    if stale:
        print(
            f"\nFAIL: {len(stale)} stale allowlist entr"
            f"{'y' if len(stale) == 1 else 'ies'} in {args.allowlist} — "
            "delete them, the thing they excused is gone:",
            file=sys.stderr,
        )
        for path, why, _entry in sorted(stale):
            print(f"  {path}: {why}", file=sys.stderr)
        return 1

    if args.fail_over is not None and len(remaining) > args.fail_over:
        print(
            f"\nFAIL: {len(remaining)} unallowed violation(s) "
            f"exceeds the allowed {args.fail_over}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
