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

  ARCHIVED_UNCHECKED_AC
                     A todo under `archive/` with at least one `- [ ]`
                     acceptance criterion that is not re-pointed. This closes the
                     half ARCHIVED_OPEN cannot see: a todo archived with
                     `status: completed` and 38 unchecked ACs passes the
                     archived-while-open rule cleanly
                     (`todos/archive/2025-11-05-011-completed-p2-sql-wildcard-
                     sanitization.md` is exactly that). An AC is excused only by
                     CLAUDE.md's re-point convention -- a named target todo,
                     marked either by an arrow (`->` or U+2192) or by the words
                     "re-pointed" next to it:
                       - [ ] #M2 bookmarks -> todo 283 (re-pointed 2026-07-26)
                     The predicate is deliberately narrow. A loose one ("see todo
                     x", "tracked in y") matches ordinary prose, and an exemption
                     that is easy to satisfy by accident is the same as no rule.
                     Zero of the 63 files carrying unchecked ACs clear it today,
                     so the exemption starts unused -- the honest starting point.

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

TWO LISTS, NOT ONE

  `todos/archive-status-allowlist.yml` holds both, keyed separately, because they
  have opposite futures: `allow` (the archived-open backlog) should shrink to
  zero as people triage, while `grandfathered_unchecked_acs` is a fixed snapshot
  of what predated the AC rule. A single shared counter would let progress in one
  bucket manufacture slack in the other.

A THIRD RULE, ON THE WORK LOG (todo 492, owner decision 2026-10-10)

  ARCHIVED_HOME_PATH An archived todo whose `## Work Log` section still names a
                     local home path: `/Users/<name>` or `/home/<name>` where a
                     path starts. Workers once recorded commands and evidence as
                     absolute worktree and venv paths. The worktree is deleted
                     after landing, so the command cannot be re-run, and the repo
                     is public, so the path leaks the home user name. Land
                     rewrites what it quotes (`land._relativize`), and refuses to
                     archive a todo whose Work Log still holds one; this rule is
                     the CI half. A path inside a longer one (`components/home/x`)
                     does not count. It is a separate pass with its own
                     grandfather list (`grandfathered_home_paths`), so a file
                     excused for another rule can never hide a home path.

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
UNCHECKED_AC_RE = re.compile(r"^\s*-\s\[ \]")
# Fenced blocks are EXAMPLES, not criteria. Two archived todos illustrate the
# convention inside ``` fences -- counting those would fail a file whose real
# criteria are all done. (044-resolved-p2-pii-logging-not-enforced.md was once
# cited here as having three boxes in fences; they were outside, hidden by a
# toggle that a ```python line inside a ```markdown block flipped -- todo 551.)
FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
# A fence's opening run (todo 551): the closer must be the same character, at least as long, and nothing else.
_FENCE_OPEN_RE = re.compile(r"^\s*(`{3,}|~{3,})")


def fenced_lines(lines):
    """One flag per line: True for a line inside a fenced block, its opening and closing lines included (todo 551).

    A fence closes only on a line of the same character, at least as long as its opener and with nothing after
    it, so a ``` line quoted inside a ```` block, or a ~~~ line inside a ``` block, is content, not a closer. An
    opener never closed before the end of the file is plain text, not a block that swallows the rest of it: a
    stray fence before `## Work Log` must not hide that section (and every home path in it) from the check."""
    flags = [False] * len(lines)
    n = 0
    while n < len(lines):
        opened = _FENCE_OPEN_RE.match(lines[n])
        if not opened:
            n += 1
            continue
        run = opened.group(1)
        closer = re.compile(rf"^\s*{re.escape(run[0])}{{{len(run)},}}\s*$")
        end = next((k for k in range(n + 1, len(lines)) if closer.match(lines[k])), None)
        if end is None:
            n += 1  # unclosed: the opener is plain text, and scanning resumes on the next line
            continue
        for k in range(n, end + 1):
            flags[k] = True
        n = end + 1
    return flags
# CLAUDE.md's re-point convention, deliberately narrow: a NUMBERED TARGET, marked
# by an arrow or by the words "re-pointed". A bare todo number is not enough --
#   - [ ] #M2 bookmarks -> todo 283 (re-pointed 2026-07-26; promoted out of 263)
# A loose predicate ("see todo", "tracked in") matches ordinary prose, and the
# whole value of this exemption is that it is HARD to satisfy. Measured against
# the repo: zero of the 63 files with unchecked ACs clear this bar, so the
# exemption starts unused -- which is the honest starting point, not a failure.
REPOINT_RE = re.compile(
    r"(?:\u2192|->)\s*todo\s*\d+|re-?pointed\b.*\btodo\s*\d+|\btodo\s*\d+\b.*re-?pointed",
    re.I,
)
STATUS_RE = re.compile(r"^status:\s*(.+?)\s*$", re.M)
INTERRUPT_RE = re.compile(r"^\s*(?:[-*+]|1[.)])\s")  # a list item that can interrupt a paragraph
HEADING_RE = re.compile(r"^\s*#{1,6}(?:\s|$)")


def continues(line):
    """True when `line` wraps the bullet above it: indented, non-blank, and not a new bullet, a heading or a
    fence. As in CommonMark, only a `1.` item can start a list inside a paragraph, and a heading needs a space
    after its #s, so a wrapped `10. ...` or `#42 ...` is text (todo 468 N2). The one rule both criteria parsers
    use (todo 572): `todofile.ac_lines` and `parse` below join a criterion's wrapped lines the same way."""
    return (line[:1] in (" ", "\t") and bool(line.strip()) and not INTERRUPT_RE.match(line)
            and not HEADING_RE.match(line) and not FENCE_RE.match(line))
# A home directory, followed by a name (todo 546 widened it):
#   - `/Users/<name>` anywhere, glued to a flag (`-I/Users/x`) or after a URL scheme (`file:///Users/x`) too.
#     A capitalised `Users` directory inside a repo path is not a thing this repo has;
#   - `/home/<name>` where a path starts, one or more slashes deep (`//home/x`, `file:///home/x`), but not after
#     a character a path name is made of, so the `home/` inside `apps/blog/templates/wagtailadmin/home/` or
#     `components/home/` is not one, and neither is a doubled slash inside a path (`apps//home/x`, todo 551): the
#     match must start at the first slash of the run. A URL route in prose (`/home/feed`) still matches: it cannot be told from a
#     home directory without knowing the user names, and the grandfather list excuses a file that needs it;
#   - the sandbox TMPDIR / project-key spelling, where `/` became `-` (`/private/tmp/claude-501/-Users-<name>-projects-...`),
#     after a `/`, a quote, a backtick or a space alike, but only when the name is followed by another `-` segment, as
#     that spelling always is: so a bare `-Users-<name>-projects-x` is one, and prose such as `a -home-made fix` or
#     `the -Users-guide` is not (todo 551, review of PR #1016);
#   - a Windows profile path (`C:\Users\<name>`).
_NAME = r"[^/\\\s'\"`;:,=|&<>()\[\]{}]+"
HOME_PATH_RE = re.compile(
    rf"/Users/{_NAME}"
    rf"|(?<![\w.~/])/+home/{_NAME}"
    r"|(?<![\w-])-(?:Users|home)-[^-/\s'\"`<>]+-"
    r"|\b[A-Za-z]:\\+Users\\+[^\\/\s'\"`;:,<>]+"
)
HOME_KIND = "ARCHIVED_HOME_PATH"

DEFAULT_ROOTS = ("todos", "backend/todos", "backend/github-issues")
ALLOWLIST_PATH = "todos/archive-status-allowlist.yml"


def parse(path):
    """Return (frontmatter_status, filename_status, has_frontmatter, bare_acs)."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    if not text.startswith("---\n"):
        return None, None, False, []
    end = text.find("\n---", 4)
    block = text[4:end] if end != -1 else text
    found = STATUS_RE.search(block)
    status = found.group(1).strip().lower() if found else None
    name_match = FILENAME_RE.match(os.path.basename(path))
    bare = []
    lines = text.splitlines()
    flags = fenced_lines(lines)
    for n, (line, fenced) in enumerate(zip(lines, flags)):
        if fenced or not UNCHECKED_AC_RE.match(line):
            continue
        # Todo 572: a criterion is its checkbox line plus the lines that wrap it, as todofile.ac_lines reads it,
        # so a re-point marker on a wrapped line counts. Matched per physical line, the engine accepted such a
        # criterion and archive refused it.
        parts, k = [line.strip()], n + 1
        while k < len(lines) and not flags[k] and continues(lines[k]):
            parts.append(lines[k].strip())
            k += 1
        if not REPOINT_RE.search(" ".join(parts)):
            bare.append(line)
    return status, (name_match.group(1).lower() if name_match else None), True, bare


def work_log_home_paths(text):
    """The lines of a todo's `## Work Log` section (to the next `## ` heading) that name a home path. A `## `
    line inside a fenced block (a quoted evidence tail) is output, not a heading: it neither ends the section
    nor starts one (todo 546), so a home path quoted after it is still found. Fences are matched by character
    and length, and an unclosed one is plain text (`fenced_lines`, todo 551)."""
    out, inside = [], False
    lines = text.splitlines()
    for line, fenced in zip(lines, fenced_lines(lines)):
        if line.startswith("## ") and not fenced:
            inside = line.rstrip() == "## Work Log"
            continue
        if inside and HOME_PATH_RE.search(line):
            out.append(line)
    return out


def scan_home_paths(roots):
    """{path: [Work Log lines naming a home path]} for every archived todo with one."""
    found = {}
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirnames, filenames in os.walk(root):
            for name in sorted(filenames):
                path = os.path.join(dirpath, name)
                if not name.endswith(".md") or name in SKIP_NAMES or f"{os.sep}archive{os.sep}" not in f"{path}{os.sep}":
                    continue
                with open(path, encoding="utf-8", errors="replace") as fh:
                    lines = work_log_home_paths(fh.read())
                if lines:
                    found[path] = lines
    return found


SEVERITY = (
    "ARCHIVED_OPEN",
    "MISSING_STATUS",
    "UNKNOWN_STATUS",
    "ARCHIVED_UNCHECKED_AC",
    "FILENAME_OVERCLAIM",
)


def scan(roots):
    """Yield one (path, kind, detail) per violating FILE, plus skipped files.

    A file can break both rules at once -- 26 of this repo's 29 do -- so the most
    serious finding wins and the count stays a count of files. That keeps the
    allowlist 1:1 with paths; an allowlist keyed on (path, rule) would let a file
    be excused for being archived-while-open and still fail on the filename, which
    reads as a bug rather than as the ratchet it is meant to be.
    """
    violations, skipped, kinds = [], [], {}
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirnames, filenames in os.walk(root):
            for name in sorted(filenames):
                if not name.endswith(".md") or name in SKIP_NAMES:
                    continue
                path = os.path.join(dirpath, name)
                status, filename_status, has_fm, bare_acs = parse(path)
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
                        if archived and bare_acs:
                            found.append(
                                (
                                    "ARCHIVED_UNCHECKED_AC",
                                    f"archived with {len(bare_acs)} unchecked acceptance "
                                    f"criteri{'on' if len(bare_acs) == 1 else 'a'} that "
                                    "are not re-pointed",
                                )
                            )
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
                    kinds[path] = {k for k, _ in found}
    return violations, skipped, kinds


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


AC_KIND = "ARCHIVED_UNCHECKED_AC"


def load_ac_grandfathers(path):
    """Return the set of paths grandfathered for unchecked acceptance criteria.

    Paths only, no per-entry reason: this is one dated historical snapshot of
    every archived todo that already had bare unchecked ACs when the rule landed,
    not 63 individual judgements. Kept in its OWN list because the two buckets
    have opposite futures -- the `allow` list above should shrink to zero as
    people triage, while this one is a fixed record of what predates the rule.
    Sharing one counter between them would let progress in one manufacture slack
    in the other.
    """
    if not os.path.exists(path):
        return set()
    import yaml

    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return set(data.get("grandfathered_unchecked_acs", []) or [])


def load_home_grandfathers(path):
    """The archived todos whose Work Log already named a home path when that rule landed (todo 492): a
    fixed snapshot, like the unchecked-AC list. An entry whose file no longer names one is stale and fails."""
    if not os.path.exists(path):
        return set()
    import yaml

    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return set(data.get("grandfathered_home_paths", []) or [])


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
    violations, skipped, kinds = scan(roots)

    allow = {} if args.no_allowlist else load_allowlist(args.allowlist)
    ac_allow = set() if args.no_allowlist else load_ac_grandfathers(args.allowlist)
    home = scan_home_paths(roots)
    home_allow = set() if args.no_allowlist else load_home_grandfathers(args.allowlist)

    # A stale entry fails. An allowlist nobody can be wrong about is an
    # allowlist nobody ever removes from.
    stale = []
    for path in allow:
        if not os.path.exists(path):
            stale.append((path, "file no longer exists"))
        elif not (kinds.get(path, set()) - {AC_KIND}):
            stale.append((path, "file no longer violates"))
    for path in ac_allow:
        if not os.path.exists(path):
            stale.append((path, "file no longer exists (unchecked-AC list)"))
        elif AC_KIND not in kinds.get(path, set()):
            stale.append((path, "file no longer has bare unchecked ACs"))
    for path in home_allow:
        if not os.path.exists(path):
            stale.append((path, "file no longer exists (home-path list)"))
        elif path not in home:
            stale.append((path, "file's Work Log no longer names a home path"))

    def excused(path, kind):
        return path in (ac_allow if kind == AC_KIND else allow)

    remaining = [v for v in violations if not excused(v[0], v[1])]
    home_remaining = sorted(p for p in home if p not in home_allow)

    by_kind = Counter(kind for _p, kind, _d in violations)
    by_kind_remaining = Counter(kind for _p, kind, _d in remaining)
    width = max([len(k) for k in by_kind] + ([len(HOME_KIND)] if home else []), default=18)
    print(f"{'violation'.ljust(width)}  total  unallowed")
    for kind in sorted(by_kind):
        print(f"{kind.ljust(width)}  {by_kind[kind]:5d}  {by_kind_remaining[kind]:9d}")
    if home:
        print(f"{HOME_KIND.ljust(width)}  {len(home):5d}  {len(home_remaining):9d}")
    print(f"{'TOTAL'.ljust(width)}  {len(violations) + len(home):5d}  {len(remaining) + len(home_remaining):9d}")

    allowed_kinds = Counter(e["kind"] for e in allow.values())
    if allow:
        print(
            f"\n{len(allow)} allowlisted "
            f"({', '.join(f'{v} {k}' for k, v in sorted(allowed_kinds.items()))})"
        )
    if ac_allow:
        print(f"{len(ac_allow)} grandfathered for unchecked acceptance criteria")
    if home_allow:
        print(f"{len(home_allow)} grandfathered for a home path in the Work Log")
    if skipped:
        print(f"{len(skipped)} file(s) skipped: no frontmatter block, cannot be judged")

    if args.list:
        print()
        for path, kind, detail in sorted(remaining):
            print(f"{path}\n    {kind}: {detail}")
        for path in home_remaining:
            print(f"{path}\n    {HOME_KIND}: the Work Log names a home path ({len(home[path])} line(s)); make it "
                  "repo-relative")
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
        for path, why in sorted(stale):
            print(f"  {path}: {why}", file=sys.stderr)
        return 1

    if args.fail_over is not None and len(remaining) + len(home_remaining) > args.fail_over:
        print(
            f"\nFAIL: {len(remaining) + len(home_remaining)} unallowed violation(s) "
            f"exceeds the allowed {args.fail_over}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
