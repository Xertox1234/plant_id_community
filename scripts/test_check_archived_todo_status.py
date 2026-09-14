#!/usr/bin/env python3
"""Tests for scripts/check_archived_todo_status.py.

Run: python3 scripts/test_check_archived_todo_status.py
Also run by .github/workflows/harness-ci.yml (a required status check).

This checker exists because an archived todo asserted a key had been rotated and
it had not; eleven months later the key was still live in a public repo (todo
390). So the cases worth testing are the ways it could report "clean" while
blind:

  - the HONEST LIAR: filename and frontmatter agree, and both say `pending`,
    under archive/. Todo 390 proposed a filename-vs-frontmatter mismatch rule;
    this repo had two such files (a CSRF bypass and a JWT lifetime) that such a
    rule waves through for being consistently wrong. `archived && open` is the
    rule that catches them, and this is the test that pins it.
  - SYNONYM NOISE must NOT fail: `completed` filename over `status: resolved` is
    24 of this repo's 50 literal string mismatches. A checker that fires on those
    gets muted, and a muted checker is the state we started from.
  - a STALE ALLOWLIST ENTRY must fail. An allowlist that cannot be wrong is an
    allowlist nobody ever removes from -- the decay documented in
    .github/security-suppressions.yml, which hid 19 advisories for two months.
  - a MALFORMED allowlist entry must exit 2 (a broken config is not a pass).
  - a file with NO frontmatter block is skipped, not failed: two such files are
    prose-era todos the frontmatter convention cannot judge, and guessing at them
    would manufacture exactly the false confidence this check opposes.
"""

import contextlib
import io
import os
import pathlib
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_archived_todo_status as chk  # noqa: E402

FAILURES = []


def check(label, condition, detail=""):
    print(f"  {'PASS' if condition else 'FAIL'}  {label}{'' if condition else f'  -- {detail}'}")
    if not condition:
        FAILURES.append(label)


def run(root, allowlist=None, fail_over=0, no_allowlist=False):
    """Run main() with argv, returning (exit_code, stdout+stderr)."""
    argv = ["check", "--root", str(root), "--fail-over", str(fail_over)]
    argv += ["--no-allowlist"] if no_allowlist else ["--allowlist", str(allowlist or "/nonexistent")]
    out, err = io.StringIO(), io.StringIO()
    old = sys.argv
    sys.argv = argv
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = chk.main()
    except SystemExit as exc:
        code = exc.code
    finally:
        sys.argv = old
    return code, out.getvalue() + err.getvalue()


def todo(dirpath, name, status, body="# t\n"):
    p = pathlib.Path(dirpath) / name
    p.parent.mkdir(parents=True, exist_ok=True)
    head = "---\n" + (f"status: {status}\n" if status is not None else "") + "---\n"
    p.write_text(head + body)
    return p


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = pathlib.Path(tmp) / "todos"
        arch = root / "archive"

        print("the honest liar -- filename and frontmatter agree, both open, under archive/")
        todo(arch, "017-pending-p2-registration-csrf-bypass.md", "pending")
        code, out = run(root, no_allowlist=True)
        check("archived + status: pending fails even with a matching filename", code == 1, out)
        check("reported as ARCHIVED_OPEN", "ARCHIVED_OPEN" in out, out)
        os.remove(arch / "017-pending-p2-registration-csrf-bypass.md")

        print("synonym noise must not fail")
        todo(arch, "010-completed-p2-x.md", "resolved")
        todo(arch, "011-complete-p2-y.md", "completed")
        todo(arch, "012-completed-p2-z.md", "complete")
        code, out = run(root, no_allowlist=True)
        check("completed/resolved/complete are one class", code == 0, out)

        print("a filename claiming done over a dropped status is an overclaim")
        todo(arch, "013-completed-p2-threadpool.md", "closed")
        code, out = run(root, no_allowlist=True)
        check("completed filename + status: closed fails", code == 1, out)
        check("reported as FILENAME_OVERCLAIM", "FILENAME_OVERCLAIM" in out, out)
        check("not miscounted as ARCHIVED_OPEN", "ARCHIVED_OPEN" not in out, out)
        os.remove(arch / "013-completed-p2-threadpool.md")

        print("terminal statuses are accepted under archive/")
        for i, status in enumerate(("completed", "resolved", "closed", "skipped", "superseded")):
            todo(arch, f"02{i}-{status}-p3-ok.md", status)
        code, out = run(root, no_allowlist=True)
        check("done + dropped classes both pass", code == 0, out)

        print("an open status outside archive/ is fine")
        todo(root, "400-pending-p2-live.md", "pending")
        code, out = run(root, no_allowlist=True)
        check("a live pending todo is not a violation", code == 0, out)

        print("unknown and missing status")
        todo(arch, "030-completed-p3-weird.md", "halfway")
        code, out = run(root, no_allowlist=True)
        check("an unrecognised status fails rather than passing", code == 1, out)
        check("reported as UNKNOWN_STATUS", "UNKNOWN_STATUS" in out, out)
        os.remove(arch / "030-completed-p3-weird.md")

        todo(arch, "031-completed-p3-nostatus.md", None)
        code, out = run(root, no_allowlist=True)
        check("frontmatter with no status: key fails", code == 1, out)
        check("reported as MISSING_STATUS", "MISSING_STATUS" in out, out)
        os.remove(arch / "031-completed-p3-nostatus.md")

        print("no frontmatter block at all is skipped, not failed")
        (arch / "007-completed-prose-era.md").write_text("# TODO 007\n\n**Status**: RESOLVED\n")
        code, out = run(root, no_allowlist=True)
        check("prose-era todo does not fail the check", code == 0, out)
        check("but is counted as skipped", "1 file(s) skipped" in out, out)

        print("the allowlist")
        bad = arch / "040-completed-p1-unfinished.md"
        todo(arch, bad.name, "ready")
        al = pathlib.Path(tmp) / "al.yml"

        al.write_text(
            f"allow:\n  - path: {bad}\n    kind: not-triaged\n"
            "    date: 2026-09-13\n    reason: grandfathered\n"
        )
        code, out = run(root, allowlist=al)
        check("a listed violation is excused", code == 0, out)
        check("and is still counted in the total column", " 1 " in out or "1  " in out, out)

        clean = arch / "041-completed-p1-fine.md"
        todo(arch, clean.name, "completed")
        al.write_text(
            f"allow:\n  - path: {bad}\n    kind: not-triaged\n"
            "    date: 2026-09-13\n    reason: grandfathered\n"
            f"  - path: {clean}\n    kind: not-triaged\n"
            "    date: 2026-09-13\n    reason: stale, this file is fine now\n"
        )
        code, out = run(root, allowlist=al)
        check("a STALE entry fails the check", code == 1, out)
        check("and says which one", "no longer violates" in out, out)

        al.write_text(
            f"allow:\n  - path: {bad}\n    kind: not-triaged\n"
            "    date: 2026-09-13\n    reason: grandfathered\n"
            "  - path: /gone/missing.md\n    kind: not-triaged\n"
            "    date: 2026-09-13\n    reason: file was deleted\n"
        )
        code, out = run(root, allowlist=al)
        check("an entry for a deleted file fails", code == 1, out)
        check("and says so", "no longer exists" in out, out)

        al.write_text(f"allow:\n  - path: {bad}\n    kind: not-triaged\n")
        code, out = run(root, allowlist=al)
        check("an entry missing reason/date exits 2, not 0", code == 2, out)

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s): {', '.join(FAILURES)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
