#!/usr/bin/env python3
"""Tests for scripts/todos/land.py.

Run: python3 scripts/todos/test_land.py (also run by harness-ci.yml).

land.py is where a checkbox becomes a claim. Pinned here: a box flips only
with the worker's pass AND the verifier's agreement AND an evidence file;
ac.json that disagrees with the todo stops everything; fenced examples are
not criteria; archive refuses bare boxes but accepts re-points; the review
doc is renamed COMPLETED only when nothing is left open.

Fix round 1 adds: archive validates fully before it writes anything (F1); a
Finding Status line is checked off by its arrow target alone, never by
"is this a re-point" (F2); flip_acs never checks off a re-pointed AC line
(F3); ac.json text that doesn't match its AC line refuses before any write
(F4); an embedded newline/backtick run in quoted text can't inject a heading
or escape its fence (F5); an evidence_path outside .sweep-evidence/ is never
read (F6); Finding Status matching is indentation/case tolerant and an
*absent* Acceptance Criteria section refuses archive -- an empty one (the
heading present, zero boxes under it) archives fine, since nothing was ever
claimed verified there (F7); the archive Work Log entry doesn't claim
evidence that was never quoted (F8).

Fix round 2 adds: the "evidence is quoted above" claim is keyed to a Verified
note for *this run_id*, not merely "some box happens to be checked" (G1); a
planned COMPLETED rename is validated in phase 1 -- destination-exists,
untracked, already-`-COMPLETED` -- so phase 2 can never fail a `git mv` (G3);
`source_review` only ever resolves inside docs/reviews/, so a `..` escape is
just another "not a review doc" value, never read or written (G4); sanitizing
uses str.splitlines() so every line-break-like separator is flattened, not
just \\r and \\n (G5); source_review without source_finding is a no-op with a
note, not a silent skip (G7).

Fix round 3 adds (H1): the planned-rename destination check is
`os.path.lexists`, not `is_file` -- a dangling-symlink or directory twin is
"something is there", not "nothing here yet". (H2): a plan carries the
review doc's *normalised*, repo-relative POSIX path, derived from the already
-resolved file `_review_path` found -- not the raw `source` string, which can
contain a `..` segment through a directory that doesn't exist and make a
plain `open()`/`git mv` refuse even though the resolved file is fine; an
absolute `source_review` is rejected outright, even one that happens to
resolve inside docs/reviews/. (H3): archive's phase 1 also refuses -- before
any write -- a todo with no frontmatter, an untracked todo, a `status`/
`source_review` value `set_fields` can't rewrite in place (multi-line), and a
missing `todos/archive/`. (H4): every quoted evidence-tail line that would
toggle the CI tripwire's naive fence detector is prefixed with a visible
marker before quoting, so a stray fence line in a tail can never hide (or
fake) a real unchecked box elsewhere in the file -- reversing round 2's "not
changing" call once the reviewer showed it can fail *open*, not just closed.
(H5, G7 corrected): a duplicate Finding Status line for this finding doesn't
just prefer "the first open one" -- every OPEN line checkable by this todo
(no target, or a target matching todo_id) is checked off together, since
they're the same shipped finding; when none is checkable, the note prefers
any line that at least names this todo (checked or not) over an arbitrary
first match, so it reads correctly in either duplicate order.

Fix round 4 adds: a directory or a dangling symlink at the todo's own archive
destination refuses in phase 1 -- asserted by a recording `git=` callback that
must never be called, since the unfixed code's phase-2 `git mv` also fails
cleanly on a dangling symlink; a `-COMPLETED` twin that git tracks but that
was deleted from disk skips the rename and leaves the twin's index entry
byte-identical; and malformed YAML frontmatter makes the CLI exit 2 with a
`land: ` message, not a traceback.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import land  # noqa: E402
import todofile  # noqa: E402
import check_archived_todo_status  # noqa: E402

FAILURES = []


def check(label, condition, detail=""):
    print(f"  {'PASS' if condition else 'FAIL'}  {label}{'' if condition else f'  -- {detail}'}")
    if not condition:
        FAILURES.append(label)


def todo_text(issue, finding, boxes):
    return (f'---\nstatus: pending\npriority: p3\nissue_id: "{issue}"\ndependencies: []\n'
            f'source_review: "docs/reviews/r.md"\nsource_finding: "{finding}"\n---\n\n# T\n\n'
            "## Acceptance Criteria\n\n" + "".join(f"- [ ] {b}\n" for b in boxes)
            + "\n```markdown\n- [ ] fenced example\n```\n\n## Work Log\n\n### d - created\n\n## Notes\n\nn\n")


def setup(tmp):
    repo = Path(tmp) / "repo"
    (repo / "todos" / "archive").mkdir(parents=True)
    (repo / "docs" / "reviews").mkdir(parents=True)
    (repo / "todos" / "archive" / ".keep").write_text("")
    (repo / "todos" / "412-pending-p3-a.md").write_text(todo_text("412", "7", ["one", "two", "three"]))
    (repo / "todos" / "413-pending-p3-b.md").write_text(
        todo_text("413", "8", ["only", "moved -> todo 500 (re-pointed 2026-09-27)"]))
    (repo / "docs" / "reviews" / "r.md").write_text(
        "# Review\n\n## Finding Status\n\n- [ ] #7 first thing → todo 412\n- [ ] #8 second → todo 413\n\n## Other\n\n- [ ] x\n")
    (repo / ".secrets.baseline").write_text('{"results": {"todos/412-pending-p3-a.md": []}}\n')
    ev = repo / ".sweep-evidence" / "g1"
    ev.mkdir(parents=True)
    for name in ("412-ac1.txt", "412-ac2.txt", "413-ac1.txt"):
        (ev / name).write_text("line a\nline b\n7 passed in 0.4s\n")
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "todos", "docs", ".secrets.baseline"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                   check=True)
    return repo


# The real box text for each fixture todo, so ac.json entries match by default
# (F4 refuses a mismatch) without every call site having to spell it out.
BOX_TEXT = {
    "412": ["one", "two", "three"],
    "413": ["only", "moved -> todo 500 (re-pointed 2026-09-27)"],
}


def entry(todo, index, passed=True, evidence=True, text=None):
    return {"todo": todo, "index": index, "text": BOX_TEXT[todo][index] if text is None else text,
            "command": f"pytest ac{index + 1}",
            "evidence_path": f".sweep-evidence/g1/{todo}-ac{index + 1}.txt" if evidence else "", "pass": passed}


def agree(todo, index, ok=True):
    return {"todo": todo, "index": index, "verified": ok, "note": ""}


def raises(fn):
    try:
        fn()
    except land.LandError as exc:
        return str(exc)
    return ""


def git_status(repo):
    return subprocess.run(["git", "-C", str(repo), "status", "--porcelain"], capture_output=True, text=True).stdout


def simple_todo_text(issue, source_review, source_finding):
    fm = f'---\nstatus: pending\npriority: p3\nissue_id: "{issue}"\ndependencies: []\n'
    if source_review is not None:
        fm += f'source_review: "{source_review}"\n'
    if source_finding is not None:
        fm += f'source_finding: "{source_finding}"\n'
    return (fm + '---\n\n# T\n\n## Acceptance Criteria\n\n- [x] done already\n\n'
                 '## Work Log\n\n### d - created\n\n## Notes\n\nn\n')


def repoint_only_text(issue):
    return (f'---\nstatus: pending\npriority: p3\nissue_id: "{issue}"\ndependencies: []\n---\n\n# T\n\n'
            "## Acceptance Criteria\n\n- [ ] moved -> todo 999 (re-pointed 2026-01-01)\n\n"
            "## Work Log\n\n### d - created\n\n## Notes\n\nn\n")


# F1/F2/F7(indent): every review-doc resolution case in one repo, keyed by todo id.
REVIEW_CASES = {
    "420": (None, None),                                 # no source_review/source_finding -> no review step
    "421": ("123", "1"),                                 # a PR reference, not a docs/reviews path
    "422": ("docs/reviews/missing.md", "2"),             # missing, but its -COMPLETED twin exists
    "423": ("docs/reviews/no-fs.md", "3"),               # no '## Finding Status' section
    "424": ("docs/reviews/has-fs.md", "99"),             # no line for this finding
    "425": ("docs/reviews/has-fs.md", "50"),             # already checked
    "426": ("docs/reviews/other-target.md", "M2"),       # arrow targets a DIFFERENT todo -> left open
    "427": ("docs/reviews/into-this.md", "M3"),          # arrow targets THIS todo -> checked off despite wording
    "428": ("docs/reviews/indented.md", "77"),           # indented, uppercase [X] -> already checked
    "431": ("docs/reviews/mixed-indent.md", "60"),       # checked off, but an indented sibling blocks the rename
    "433": ("docs/reviews/gone.md", "4"),                # a docs/reviews path, but missing with no twin either
}


def setup_reviews(tmp):
    repo = Path(tmp) / "repo"
    (repo / "todos" / "archive").mkdir(parents=True)
    (repo / "docs" / "reviews").mkdir(parents=True)
    (repo / "todos" / "archive" / ".keep").write_text("")
    for issue, (source_review, source_finding) in REVIEW_CASES.items():
        (repo / "todos" / f"{issue}-pending-p3-x.md").write_text(
            simple_todo_text(issue, source_review, source_finding))
    (repo / "todos" / "432-pending-p3-x.md").write_text(repoint_only_text("432"))
    (repo / "docs/reviews/missing-COMPLETED.md").write_text("# done\n")
    (repo / "docs/reviews/no-fs.md").write_text("# Review\n\n## Other\n\n- [ ] y\n")
    (repo / "docs/reviews/has-fs.md").write_text(
        "# Review\n\n## Finding Status\n\n- [x] #50 already → todo 425 (completed 2026-01-01)\n\n"
        "## Other\n\n- [ ] z\n")
    (repo / "docs/reviews/other-target.md").write_text(
        "# Review\n\n## Finding Status\n\n- [ ] #M2 bookmarks → todo 283 "
        "(re-pointed 2026-07-26; promoted out of 426)\n")
    (repo / "docs/reviews/into-this.md").write_text(
        "# Review\n\n## Finding Status\n\n- [ ] #M3 x → todo 427 (re-pointed 2026-07-26; promoted out of 263)\n")
    (repo / "docs/reviews/indented.md").write_text(
        "# Review\n\n## Finding Status\n\n  - [X] #77 indented and upper\n")
    (repo / "docs/reviews/mixed-indent.md").write_text(
        "# Review\n\n## Finding Status\n\n- [ ] #60 x → todo 431\n  - [ ] #61 y (indented, untouched)\n")
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "todos", "docs"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                   check=True)
    return repo


def main():
    with tempfile.TemporaryDirectory() as tmp:
        repo = setup(tmp)
        rel = "todos/412-pending-p3-a.md"

        msg = raises(lambda: land.flip_acs(repo, rel, [entry("412", 0), entry("412", 1)], [], "r", "2026-09-27"))
        check("count mismatch refuses", "has 3 criteria" in msg, msg)
        check("a refusal changes nothing", "- [x]" not in (repo / rel).read_text())

        flipped, left = land.flip_acs(
            repo, rel,
            [entry("412", 0), entry("412", 1, passed=True), entry("412", 2, evidence=False)],
            [agree("412", 0), agree("412", 1, ok=False), agree("412", 2)],
            "r", "2026-09-27")
        text = (repo / rel).read_text()
        check("only pass + verifier agreement + evidence flips", flipped == [0] and left == [1, 2], (flipped, left))
        check("the verifier's disagreement leaves the box open", "- [ ] two" in text)
        check("missing evidence is not flipped", "- [ ] three" in text)
        check("fenced boxes are ignored", "- [ ] fenced example" in text)
        check("the Work Log quotes the evidence tail before ## Notes",
              "7 passed in 0.4s" in text and text.index("Verified by the todo sweep") < text.index("## Notes"), text)

        msg = raises(lambda: land.archive(repo, rel, "r", "2026-09-27"))
        check("archive refuses bare unchecked criteria", "2 unchecked" in msg, msg)

        land.flip_acs(repo, rel, [entry("412", 0), entry("412", 1), entry("412", 2)],
                      [agree("412", 0), agree("412", 1), agree("412", 2)], "r", "2026-09-27")
        (repo / ".sweep-evidence/g1/412-ac3.txt").write_text("ok\n")
        land.flip_acs(repo, rel, [entry("412", 0), entry("412", 1), entry("412", 2)],
                      [agree("412", 0), agree("412", 1), agree("412", 2)], "r", "2026-09-27")
        result = land.archive(repo, rel, "r", "2026-09-27")
        dest = repo / "todos/archive/412-completed-p3-a.md"
        check("archive moves filename and status together",
              dest.exists() and todofile.read_frontmatter(dest)["status"] == "completed", result)
        check("the baseline path follows the rename",
              '"todos/archive/412-completed-p3-a.md"' in (repo / ".secrets.baseline").read_text())
        review = (repo / "docs/reviews/r.md").read_text()
        check("the source finding is checked off with a date",
              "- [x] #7 first thing → todo 412 (completed 2026-09-27)" in review, review)
        check("the review doc stays while a finding is open", result["review"]["renamed"] is False)
        check("paths to stage include the archived todo and review doc",
              {"todos/archive/412-completed-p3-a.md", "docs/reviews/r.md", ".secrets.baseline"} <= set(result["paths"]),
              result["paths"])

        # F5c: the archive gate must agree with the CI tripwire on the file it just archived.
        _, _, _, bare = check_archived_todo_status.parse(str(dest))
        check("F5c: the CI tripwire reports no bare unchecked boxes for the archived file", bare == [], bare)

        # F1: a second archive of an already-archived todo raises and changes nothing.
        before_status = git_status(repo)
        msg = raises(lambda: land.archive(repo, rel, "r", "2026-09-27"))
        check("F1: re-archiving an already-archived todo refuses", "already archived" in msg, msg)
        check("F1: the refusal leaves git status unchanged", git_status(repo) == before_status)

        rel2 = "todos/413-pending-p3-b.md"
        land.flip_acs(repo, rel2, [entry("413", 0), entry("413", 1, passed=False)], [agree("413", 0)], "r", "d")
        result = land.archive(repo, rel2, "r", "2026-09-27")
        check("a re-pointed criterion does not block archive", result["archived"].endswith("413-completed-p3-b.md"))
        check("the last finding renames the review doc COMPLETED",
              result["review"]["renamed"] and (repo / "docs/reviews/r-COMPLETED.md").exists(), result)
        check("the todo's source_review follows the rename",
              todofile.read_frontmatter(repo / result["archived"])["source_review"] == "docs/reviews/r-COMPLETED.md")
        check("468: an archived sibling todo that named the review doc follows the rename, and is staged",
              todofile.read_frontmatter(repo / "todos/archive/412-completed-p3-a.md")["source_review"]
              == "docs/reviews/r-COMPLETED.md" and "todos/archive/412-completed-p3-a.md" in result["paths"],
              (todofile.read_frontmatter(repo / "todos/archive/412-completed-p3-a.md"), result["paths"]))
        check("findings outside ## Finding Status are not counted",
              "- [ ] x" in (repo / "docs/reviews/r-COMPLETED.md").read_text())

    # F1/G6: a validation failure (destination already exists) leaves git status
    # untouched. The todo is otherwise fully archivable (all boxes really checked,
    # real evidence for every one), so the destination check is the ONLY thing
    # that can be refusing it -- not incidentally papered over by the bare-box gate.
    with tempfile.TemporaryDirectory() as tmp:
        repo = setup(tmp)
        rel = "todos/412-pending-p3-a.md"
        (repo / ".sweep-evidence/g1/412-ac3.txt").write_text("ok\n")
        land.flip_acs(repo, rel, [entry("412", 0), entry("412", 1), entry("412", 2)],
                      [agree("412", 0), agree("412", 1), agree("412", 2)], "r", "2026-09-27")
        check("G6: the fixture is genuinely fully archivable before the squat",
              check_archived_todo_status.parse(str(repo / rel))[3] == [])
        (repo / "todos/archive/412-completed-p3-a.md").write_text("squatter\n")
        before_status = git_status(repo)
        msg = raises(lambda: land.archive(repo, rel, "r", "2026-09-27"))
        check("F1: a pre-existing destination refuses", "already exists" in msg, msg)
        check("F1: that refusal leaves git status unchanged", git_status(repo) == before_status)

    # F1/F2/F7(indent): every review-doc resolution case, one repo, one archive() call each.
    with tempfile.TemporaryDirectory() as tmp:
        repo = setup_reviews(tmp)

        def review_of(issue):
            result = land.archive(repo, f"todos/{issue}-pending-p3-x.md", "r", "2026-09-27")
            return result

        r420 = review_of("420")
        check("F1: no source_review/source_finding -> no review step", r420["review"] is None, r420)

        r421 = review_of("421")
        check("F1: a PR reference (not a docs/reviews path) is a no-op",
              r421["review"]["note"] == "source_review is not a review doc: 123"
              and r421["review"]["renamed"] is False, r421)

        r422 = review_of("422")
        check("F1: a missing path with a -COMPLETED twin is a no-op naming the twin",
              "missing-COMPLETED.md" in r422["review"]["note"] and r422["review"]["renamed"] is False, r422)

        r433 = review_of("433")
        check("F1: a docs/reviews path that is plain missing (no twin either) is a no-op, not a raise",
              r433["review"]["note"] == "source_review is not a review doc: docs/reviews/gone.md"
              and r433["review"]["renamed"] is False, r433)

        r423 = review_of("423")
        check("F1: no '## Finding Status' section is a no-op",
              "Finding Status" in r423["review"]["note"] and r423["review"]["renamed"] is False, r423)

        r424 = review_of("424")
        check("F1: no line for this finding is a no-op",
              "no line for finding #99" in r424["review"]["note"], r424)

        r425 = review_of("425")
        check("F1: an already-[x] line is a no-op", r425["review"]["note"] == "already checked", r425)

        r426 = review_of("426")
        check("F2: an arrow targeting a DIFFERENT todo leaves the line open",
              r426["review"]["renamed"] is False and "targets todo 283" in r426["review"]["note"], r426)
        check("F2: the other-target line is untouched on disk",
              "- [ ] #M2 bookmarks" in (repo / "docs/reviews/other-target.md").read_text())

        r427 = review_of("427")
        check("F2: an arrow targeting THIS todo is checked off despite 're-pointed' wording",
              r427["review"]["renamed"] is True, r427)
        into_this = (repo / "docs/reviews/into-this-COMPLETED.md").read_text()
        check("F2: the checked-off line still carries its original re-pointed wording",
              "re-pointed 2026-07-26" in into_this and "- [x] #M3 x → todo 427" in into_this, into_this)

        r428 = review_of("428")
        check("F7: an indented, uppercase [X] line reads as already checked",
              r428["review"]["note"] == "already checked", r428)

        r431 = review_of("431")
        check("F7: still-open detection matches an indented sibling line, blocking the rename",
              r431["review"]["renamed"] is False, r431)
        mixed = (repo / "docs/reviews/mixed-indent.md").read_text()
        check("F7: the matched line was still checked off even though the rename was blocked",
              "- [x] #60 x" in mixed, mixed)

        # F8: zero boxes were ever flipped with evidence (this AC is a bare re-point) --
        # the Work Log must not claim evidence that was never quoted.
        r432 = review_of("432")
        note432 = (repo / r432["archived"]).read_text()
        check("F8: no 'evidence is quoted above' claim when nothing was flipped",
              "evidence is quoted above" not in note432 and "review is on the PR" in note432, note432)

    # F3: flip_acs never checks off a re-pointed AC line, even with pass + agreement + evidence.
    with tempfile.TemporaryDirectory() as tmp:
        repo = setup(tmp)
        rel2 = "todos/413-pending-p3-b.md"
        (repo / ".sweep-evidence/g1/413-ac2.txt").write_text("line a\nline b\n1 passed in 0.1s\n")
        flipped, left = land.flip_acs(repo, rel2, [entry("413", 0), entry("413", 1)],
                                      [agree("413", 0), agree("413", 1)], "r", "2026-09-27")
        check("F3: a re-pointed AC line is skipped even with pass + agreement + evidence",
              flipped == [0] and 1 not in flipped, (flipped, left))
        check("F3: the re-pointed line's checkbox is untouched",
              "- [ ] moved -> todo 500" in (repo / rel2).read_text())

    # F4: same count, swapped indexes -- refuses before any write.
    with tempfile.TemporaryDirectory() as tmp:
        repo = setup(tmp)
        rel = "todos/412-pending-p3-a.md"
        before = (repo / rel).read_text()
        swapped = [entry("412", 0, text="two"), entry("412", 1, text="one"), entry("412", 2)]
        verdicts = [agree("412", 0), agree("412", 1), agree("412", 2)]
        msg = raises(lambda: land.flip_acs(repo, rel, swapped, verdicts, "r", "2026-09-27"))
        check("F4: ac.json text that doesn't match its AC line refuses", "does not match" in msg, msg)
        check("F4: that refusal leaves the file unchanged", (repo / rel).read_text() == before)

    # F5a: an embedded newline in `command` cannot forge a new Work Log heading.
    with tempfile.TemporaryDirectory() as tmp:
        repo = setup(tmp)
        rel = "todos/412-pending-p3-a.md"
        (repo / ".sweep-evidence/g1/412-ac3.txt").write_text("ok\n")
        mal = entry("412", 0)
        mal["command"] = "pytest ac1\n## injected"
        flipped, left = land.flip_acs(repo, rel, [mal, entry("412", 1), entry("412", 2)],
                                      [agree("412", 0), agree("412", 1), agree("412", 2)], "r", "2026-09-27")
        text = (repo / rel).read_text()
        check("F5a: all three still flip in one pass", flipped == [0, 1, 2], (flipped, left))
        check("F5a: no heading was injected via an embedded newline in `command`",
              sum(1 for line in text.splitlines() if line.startswith("## ")) == 3, text)
        check("F5a: the sanitized command appears flattened to one line",
              "pytest ac1 ## injected" in text, text)
        result = land.archive(repo, rel, "r", "2026-09-27")
        dest_text = (repo / result["archived"]).read_text()
        check("F5a: the Completed entry still lands after the Verified note",
              dest_text.index("Verified by the todo sweep") < dest_text.index("Completed by the todo sweep"),
              dest_text)

    # F5b: a fenced evidence tail cannot escape its own quoting fence.
    with tempfile.TemporaryDirectory() as tmp:
        repo = setup(tmp)
        rel = "todos/412-pending-p3-a.md"
        (repo / ".sweep-evidence/g1/412-ac1.txt").write_text("before\n```\nmiddle\n```\nafter\n")
        flipped, left = land.flip_acs(repo, rel, [entry("412", 0), entry("412", 1), entry("412", 2)],
                                      [agree("412", 0), agree("412", 1), agree("412", 2)], "r", "2026-09-27")
        text = (repo / rel).read_text()
        fence_match = re.search(r"last lines:\n\n  (`{3,})text\n", text)
        check("F5b: a fence longer than the tail's own backtick run is used",
              bool(fence_match) and len(fence_match.group(1)) >= 4, text)
        if fence_match:
            check("F5b: the tail's embedded ``` stays inside the (longer) fence",
                  text.count(fence_match.group(1)) == 2, text)

    # F6: evidence_path must resolve inside <repo>/.sweep-evidence/, or it counts as missing.
    with tempfile.TemporaryDirectory() as tmp:
        repo = setup(tmp)
        rel = "todos/412-pending-p3-a.md"
        (repo / ".sweep-evidence/g1/412-ac3.txt").write_text("ok\n")
        bad = [entry("412", 0), entry("412", 1), entry("412", 2)]
        bad[0]["evidence_path"] = "/etc/hosts"
        bad[1]["evidence_path"] = "../x"
        flipped, left = land.flip_acs(repo, rel, bad,
                                      [agree("412", 0), agree("412", 1), agree("412", 2)], "r", "2026-09-27")
        check("F6: an absolute evidence_path is not flipped", 0 not in flipped, flipped)
        check("F6: a path escaping .sweep-evidence is not flipped", 1 not in flipped, flipped)
        check("F6: a valid evidence_path still flips normally", 2 in flipped, flipped)

    # F6: evidence_path must be RELATIVE, independent of containment -- an absolute
    # path that happens to RESOLVE inside .sweep-evidence/ is still not relative, and
    # must still be rejected (this is a separate guard from is_relative_to: removing
    # only the absolute check, leaving containment intact, must still fail this case).
    with tempfile.TemporaryDirectory() as tmp:
        repo = setup(tmp)
        rel = "todos/412-pending-p3-a.md"
        absolute_but_contained = [entry("412", 0), entry("412", 1), entry("412", 2)]
        absolute_but_contained[0]["evidence_path"] = str((repo / ".sweep-evidence/g1/412-ac1.txt").resolve())
        flipped, left = land.flip_acs(repo, rel, absolute_but_contained,
                                      [agree("412", 0), agree("412", 1), agree("412", 2)], "r", "2026-09-27")
        check("F6: an absolute evidence_path is rejected even when it resolves inside .sweep-evidence/",
              0 not in flipped, flipped)

    # G6: '../x' and a symlink under .sweep-evidence/ must each point at a file that
    # REALLY EXISTS and carries a marker -- otherwise "not flipped" proves nothing,
    # since a nonexistent target is never flipped regardless of containment.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / ".sweep-evidence" / "g").mkdir(parents=True)
        (repo / "todos").mkdir()
        (repo / "todos" / "470-pending-p3-x.md").write_text(
            '---\nstatus: pending\npriority: p3\nissue_id: "470"\ndependencies: []\n---\n\n# T\n\n'
            "## Acceptance Criteria\n\n- [ ] a\n- [ ] b\n\n"
            "## Work Log\n\n### d - created\n\n## Notes\n\nn\n")
        secret = Path(tmp) / "secret.txt"
        secret.write_text("SECRET_MARKER\n")
        os.symlink(secret, repo / ".sweep-evidence/g/link.txt")
        entries = [
            {"todo": "470", "index": 0, "text": "a", "command": "pytest", "evidence_path": "../secret.txt",
             "pass": True},
            {"todo": "470", "index": 1, "text": "b", "command": "pytest",
             "evidence_path": ".sweep-evidence/g/link.txt", "pass": True},
        ]
        flipped, left = land.flip_acs(repo, "todos/470-pending-p3-x.md", entries,
                                      [agree("470", 0), agree("470", 1)], "r", "2026-09-27")
        text470 = (repo / "todos/470-pending-p3-x.md").read_text()
        check("G6: '../x' pointing at a real, existing file is still not flipped", 0 not in flipped, flipped)
        check("G6: a symlink under .sweep-evidence/ pointing outside is still not flipped",
              1 not in flipped, flipped)
        check("G6: neither target's marker ever appears in the todo", "SECRET_MARKER" not in text470, text470)

    # F7: no '## Acceptance Criteria' section at all refuses archive's phase 1, cleanly.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        (repo / "todos" / "440-pending-p3-noac.md").write_text(
            '---\nstatus: pending\npriority: p3\nissue_id: "440"\ndependencies: []\n---\n\n# T\n\n'
            "## Work Log\n\n### d - created\n\n## Notes\n\nn\n")
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "todos"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        before_status = git_status(repo)
        msg = raises(lambda: land.archive(repo, "todos/440-pending-p3-noac.md", "r", "2026-09-27"))
        check("F7: a todo with no Acceptance Criteria section refuses archive",
              "Acceptance Criteria" in msg, msg)
        check("F7: that refusal leaves git status unchanged", git_status(repo) == before_status)

    # F7: truthiness -- a truthy-but-not-True pass/verified never counts.
    with tempfile.TemporaryDirectory() as tmp:
        repo = setup(tmp)
        rel = "todos/412-pending-p3-a.md"
        (repo / ".sweep-evidence/g1/412-ac3.txt").write_text("ok\n")
        entries = [entry("412", 0), entry("412", 1), entry("412", 2)]
        verdicts = [agree("412", 0), agree("412", 1), agree("412", 2)]
        verdicts[0]["verified"] = "true"
        entries[1]["pass"] = "true"
        flipped, left = land.flip_acs(repo, rel, entries, verdicts, "r", "2026-09-27")
        check("F7: a truthy-but-not-True verifier verdict does not count", 0 not in flipped, flipped)
        check("F7: a truthy-but-not-True pass does not count", 1 not in flipped, flipped)
        check("F7: a real True/True box still flips", flipped == [2], flipped)

    # G6/F5c: a stray '- [ ]' OUTSIDE the Acceptance Criteria section (in the Work
    # Log) must still refuse archive -- this is the case an AC-section-only gate
    # would miss, which is exactly why F5c uses the CI tripwire's whole-file check.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        (repo / "todos" / "480-pending-p3-x.md").write_text(
            '---\nstatus: pending\npriority: p3\nissue_id: "480"\ndependencies: []\n---\n\n# T\n\n'
            "## Acceptance Criteria\n\n- [x] a\n\n"
            "## Work Log\n\n### d - created\n\n- [ ] stray sub-task\n\n## Notes\n\nn\n")
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "todos"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        before_status = git_status(repo)
        msg = raises(lambda: land.archive(repo, "todos/480-pending-p3-x.md", "r", "2026-09-27"))
        check("G6/F5c: a stray '- [ ]' outside the AC section still refuses archive",
              "unchecked criteria" in msg, msg)
        check("G6/F5c: that refusal leaves git status unchanged", git_status(repo) == before_status)

    # G7: an EMPTY Acceptance Criteria section (the heading present, no boxes under
    # it) archives fine -- nothing was ever claimed verified there to leave unchecked.
    # Only an ABSENT section (tested under F7 above) refuses.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        (repo / "todos" / "481-pending-p3-x.md").write_text(
            '---\nstatus: pending\npriority: p3\nissue_id: "481"\ndependencies: []\n---\n\n# T\n\n'
            "## Acceptance Criteria\n\n## Work Log\n\n### d - created\n\n## Notes\n\nn\n")
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "todos"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        result = land.archive(repo, "todos/481-pending-p3-x.md", "r", "2026-09-27")
        check("G7: an empty (but present) Acceptance Criteria section archives fine",
              result["archived"].endswith("481-completed-p3-x.md"), result)

    # G1: a box that was already [x] with no Verified note for this land (never flipped
    # here) must not claim "evidence is quoted above" -- any_checked alone proves nothing.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        (repo / "todos" / "482-pending-p3-x.md").write_text(
            '---\nstatus: pending\npriority: p3\nissue_id: "482"\ndependencies: []\n---\n\n# T\n\n'
            "## Acceptance Criteria\n\n- [x] already done\n\n## Work Log\n\n### d - created\n\n## Notes\n\nn\n")
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "todos"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        result = land.archive(repo, "todos/482-pending-p3-x.md", "r", "2026-09-27")
        note482 = (repo / result["archived"]).read_text()
        check("G1: a pre-checked box with no Verified note for this run does not claim evidence was quoted",
              "evidence is quoted above" not in note482 and "Verified by" not in note482, note482)

    # G3: a planned COMPLETED rename is validated in phase 1, so a collision or an
    # untracked doc downgrades to "checked off, no rename" -- never a phase-2 exception.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "docs" / "reviews").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        (repo / "todos" / "490-pending-p3-x.md").write_text(simple_todo_text("490", "docs/reviews/g3a.md", "1"))
        (repo / "docs/reviews/g3a.md").write_text("# R\n\n## Finding Status\n\n- [ ] #1 x → todo 490\n")
        (repo / "docs/reviews/g3a-COMPLETED.md").write_text("# old, unrelated\n")  # destination collision
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        result = land.archive(repo, "todos/490-pending-p3-x.md", "r", "2026-09-27")
        check("G3: a colliding -COMPLETED destination skips the rename, no exception",
              result["review"]["renamed"] is False and "already exists" in result["review"]["note"], result)
        check("G3: the finding was still checked off despite the skipped rename",
              "- [x] #1 x" in (repo / "docs/reviews/g3a.md").read_text())
        check("G3: the collided destination file is untouched",
              (repo / "docs/reviews/g3a-COMPLETED.md").read_text() == "# old, unrelated\n")

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "docs" / "reviews").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        (repo / "todos" / "491-pending-p3-x.md").write_text(simple_todo_text("491", "docs/reviews/g3b.md", "1"))
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "todos"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        # g3b.md exists on disk but is never `git add`-ed -- untracked.
        (repo / "docs/reviews/g3b.md").write_text("# R\n\n## Finding Status\n\n- [ ] #1 x → todo 491\n")
        result = land.archive(repo, "todos/491-pending-p3-x.md", "r", "2026-09-27")
        check("G3: an untracked review doc skips the rename, no exception",
              result["review"]["renamed"] is False and "not tracked in git" in result["review"]["note"], result)
        check("G3: the finding was still checked off despite the untracked doc",
              "- [x] #1 x" in (repo / "docs/reviews/g3b.md").read_text())

    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "docs" / "reviews").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        (repo / "todos" / "492-pending-p3-x.md").write_text(
            simple_todo_text("492", "docs/reviews/g3c-COMPLETED.md", "1"))
        (repo / "docs/reviews/g3c-COMPLETED.md").write_text("# R\n\n## Finding Status\n\n- [ ] #1 x → todo 492\n")
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        result = land.archive(repo, "todos/492-pending-p3-x.md", "r", "2026-09-27")
        check("G3: a source already ending in -COMPLETED.md is never renamed again",
              result["review"]["renamed"] is False
              and not (repo / "docs/reviews/g3c-COMPLETED-COMPLETED.md").exists(), result)

    # G4: source_review resolving outside docs/reviews/ (via '..') is a no-op -- the
    # outside file is never read or written, and archive succeeds anyway.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "docs" / "reviews").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        (repo / "todos" / "493-pending-p3-x.md").write_text(
            simple_todo_text("493", "docs/reviews/../../../outside.md", "1"))
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "todos", "docs"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        outside = Path(tmp) / "outside.md"
        outside_before = "# O\n\n## Finding Status\n\n- [ ] #1 x → todo 493\n"
        outside.write_text(outside_before)
        result = land.archive(repo, "todos/493-pending-p3-x.md", "r", "2026-09-27")
        check("G4: a source_review escaping docs/reviews/ is a no-op",
              result["review"]["note"] == "source_review is not a review doc: docs/reviews/../../../outside.md",
              result)
        check("G4: the outside file is never read or written", outside.read_text() == outside_before)
        check("G4: archive itself still succeeds", result["archived"].endswith("493-completed-p3-x.md"))

    # G5: str.splitlines()-based sanitizing must flatten every line-break-like
    # separator, not just \r and \n -- the reviewer's Probe B variant.
    for sep in (" ", "\x85", "\x0c"):
        with tempfile.TemporaryDirectory() as tmp:
            repo = setup(tmp)
            rel = "todos/412-pending-p3-a.md"
            (repo / ".sweep-evidence/g1/412-ac3.txt").write_text("ok\n")
            mal = entry("412", 0)
            mal["command"] = f"pytest ac1{sep}## injected{sep}- [ ] fake"
            land.flip_acs(repo, rel, [mal, entry("412", 1), entry("412", 2)],
                          [agree("412", 0), agree("412", 1), agree("412", 2)], "r", "2026-09-27")
            result = land.archive(repo, rel, "r", "2026-09-27")
            dest_text = (repo / result["archived"]).read_text()
            check(f"G5: separator {sep!r} does not break archive or displace the Completed entry",
                  dest_text.index("Verified by the todo sweep") < dest_text.index("Completed by the todo sweep"),
                  dest_text)
            check(f"G5: separator {sep!r} does not survive as its own line",
                  sum(1 for line in dest_text.splitlines() if line.startswith("## ")) == 3, dest_text)

    # G7: several Finding Status lines can name the same finding (a stale, already-
    # checked one plus the live one) -- the first OPEN match is what gets checked off.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "docs" / "reviews").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        (repo / "todos" / "521-pending-p3-x.md").write_text(simple_todo_text("521", "docs/reviews/g7a.md", "1"))
        (repo / "docs/reviews/g7a.md").write_text(
            "# R\n\n## Finding Status\n\n- [x] #1 old → todo 300 (completed 2026-01-01)\n"
            "- [ ] #1 again → todo 521\n")
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        result = land.archive(repo, "todos/521-pending-p3-x.md", "r", "2026-09-27")
        g7a = (repo / "docs/reviews/g7a.md").read_text() if not result["review"]["renamed"] \
            else (repo / "docs/reviews/g7a-COMPLETED.md").read_text()
        check("G7: the stale, already-checked duplicate line is untouched",
              "#1 old → todo 300 (completed 2026-01-01)" in g7a, g7a)
        check("G7: the live, open duplicate line (matching this todo) was the one checked off",
              "- [x] #1 again → todo 521 (completed 2026-09-27)" in g7a, g7a)

    # G7: the reverse duplicate order -- THIS todo's own line was already checked, and
    # a LATER re-point of the same finding number (open, targeting someone else) was
    # appended after it. Archiving this todo again must still read "already checked",
    # not get shadowed by the later, irrelevant open line just because it's open.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "docs" / "reviews").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        (repo / "todos" / "530-pending-p3-x.md").write_text(simple_todo_text("530", "docs/reviews/g7b.md", "M2"))
        (repo / "docs/reviews/g7b.md").write_text(
            "# R\n\n## Finding Status\n\n- [x] #M2 x → todo 530 (completed 2026-01-01)\n"
            "- [ ] #M2 y → todo 999 (re-pointed 2026-02-01; promoted out of 530)\n")
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        result = land.archive(repo, "todos/530-pending-p3-x.md", "r", "2026-09-27")
        g7b = (repo / "docs/reviews/g7b.md").read_text()
        check("G7: this todo's own already-checked line reads as already checked, "
              "not shadowed by a later re-point of the same finding to someone else",
              result["review"]["note"] == "already checked", result)
        check("G7: the later re-point line (targeting a different todo) is untouched",
              "- [ ] #M2 y → todo 999" in g7b, g7b)

    # G7: source_review set without source_finding is a no-op with a note, not a
    # silent skip indistinguishable from "no source_review at all".
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        (repo / "todos" / "522-pending-p3-x.md").write_text(
            '---\nstatus: pending\npriority: p3\nissue_id: "522"\ndependencies: []\n'
            'source_review: "docs/reviews/whatever.md"\n---\n\n# T\n\n'
            "## Acceptance Criteria\n\n- [x] a\n\n## Work Log\n\n### d - created\n\n## Notes\n\nn\n")
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "todos"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        result = land.archive(repo, "todos/522-pending-p3-x.md", "r", "2026-09-27")
        check("G7: source_review without source_finding is a no-op with a note",
              result["review"] is not None and "source_finding is missing" in result["review"]["note"], result)

    # H1: a dangling-symlink twin at the -COMPLETED destination must skip the
    # rename with a note, never raise (is_file() misses a dangling symlink).
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "docs" / "reviews").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        (repo / "todos" / "540-pending-p3-x.md").write_text(simple_todo_text("540", "docs/reviews/h1a.md", "1"))
        (repo / "docs/reviews/h1a.md").write_text("# R\n\n## Finding Status\n\n- [ ] #1 x → todo 540\n")
        os.symlink("nowhere.md", repo / "docs/reviews/h1a-COMPLETED.md")
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "todos", "docs/reviews/h1a.md"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        result = land.archive(repo, "todos/540-pending-p3-x.md", "r", "2026-09-27")
        check("H1: a dangling-symlink twin skips the rename with a note, no exception",
              result["review"]["renamed"] is False and "already exists" in result["review"]["note"], result)
        check("H1: the review doc itself was still checked off",
              "- [x] #1 x" in (repo / "docs/reviews/h1a.md").read_text())
        check("H1: the dangling symlink itself is untouched, not moved into",
              os.path.islink(repo / "docs/reviews/h1a-COMPLETED.md"))

    # H1: a directory sitting at the -COMPLETED destination must also skip the
    # rename with a note -- not have the doc moved INTO the directory by git mv.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "docs" / "reviews").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        (repo / "todos" / "541-pending-p3-x.md").write_text(simple_todo_text("541", "docs/reviews/h1b.md", "1"))
        (repo / "docs/reviews/h1b.md").write_text("# R\n\n## Finding Status\n\n- [ ] #1 x → todo 541\n")
        (repo / "docs/reviews/h1b-COMPLETED.md").mkdir()
        (repo / "docs/reviews/h1b-COMPLETED.md/keep.txt").write_text("k\n")
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        result = land.archive(repo, "todos/541-pending-p3-x.md", "r", "2026-09-27")
        check("H1: a directory twin skips the rename with a note, no exception",
              result["review"]["renamed"] is False and "already exists" in result["review"]["note"], result)
        check("H1: the review doc was checked off, not moved into the directory",
              "- [x] #1 x" in (repo / "docs/reviews/h1b.md").read_text())
        check("H1: the directory twin's own content is untouched",
              (repo / "docs/reviews/h1b-COMPLETED.md/keep.txt").read_text() == "k\n")

    # H2: 'docs/reviews/nope/../h2a.md' -- 'nope' does NOT exist -- must archive
    # (not FileNotFoundError from a naive open() on the un-normalised raw string),
    # and the returned paths must be the clean, normalised, repo-relative form.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "docs" / "reviews").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        (repo / "todos" / "550-pending-p3-x.md").write_text(
            simple_todo_text("550", "docs/reviews/nope/../h2a.md", "1"))
        (repo / "docs/reviews/h2a.md").write_text("# R\n\n## Finding Status\n\n- [ ] #1 x → todo 550\n")
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        result = land.archive(repo, "todos/550-pending-p3-x.md", "r", "2026-09-27")
        check("H2: a '..' through a NONEXISTENT directory still archives",
              result["archived"].endswith("550-completed-p3-x.md"), result)
        check("H2: the returned paths are normalised (no dot-segments)",
              "docs/reviews/h2a-COMPLETED.md" in result["paths"]
              and not any(".." in p for p in result["paths"]), result["paths"])

    # H2: 'docs/reviews/sub/../h2b.md' -- 'sub' DOES exist -- returned paths (and the
    # archived todo's own source_review) must still be the normalised form, not the
    # literal dotted string.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "docs" / "reviews" / "sub").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        (repo / "todos" / "551-pending-p3-x.md").write_text(
            simple_todo_text("551", "docs/reviews/sub/../h2b.md", "1"))
        (repo / "docs/reviews/h2b.md").write_text("# R\n\n## Finding Status\n\n- [ ] #1 x → todo 551\n")
        (repo / "docs/reviews/sub/keep.txt").write_text("k\n")
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        result = land.archive(repo, "todos/551-pending-p3-x.md", "r", "2026-09-27")
        check("H2: a '..' through an EXISTING directory also gets normalised paths",
              "docs/reviews/h2b-COMPLETED.md" in result["paths"]
              and not any(".." in p for p in result["paths"]), result["paths"])
        check("H2: the archived todo's own source_review is normalised too",
              todofile.read_frontmatter(repo / result["archived"])["source_review"]
              == "docs/reviews/h2b-COMPLETED.md")

    # H2: an absolute source_review, even one that resolves inside docs/reviews/, is a
    # no-op -- never stamped into the todo's own frontmatter as a machine-specific path.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "docs" / "reviews").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        abs_review = str((repo / "docs/reviews/h2c.md").resolve())
        (repo / "todos" / "552-pending-p3-x.md").write_text(simple_todo_text("552", abs_review, "1"))
        (repo / "docs/reviews/h2c.md").write_text("# R\n\n## Finding Status\n\n- [ ] #1 x → todo 552\n")
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        result = land.archive(repo, "todos/552-pending-p3-x.md", "r", "2026-09-27")
        check("H2: an absolute source_review that resolves inside docs/reviews/ is still a no-op",
              result["review"]["note"] == f"source_review is not a review doc: {abs_review}"
              and result["review"]["renamed"] is False, result)
        check("H2: the review doc itself was never touched",
              "- [ ] #1 x" in (repo / "docs/reviews/h2c.md").read_text())

    # H3: a todo with no frontmatter block at all refuses cleanly in phase 1.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        (repo / "todos" / "560-pending-p3-x.md").write_text(
            "# T\n\n## Acceptance Criteria\n\n- [x] a\n\n## Work Log\n\n### d - created\n\n## Notes\n\nn\n")
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "todos"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        before_status = git_status(repo)
        msg = raises(lambda: land.archive(repo, "todos/560-pending-p3-x.md", "r", "2026-09-27"))
        check("H3: a todo with no frontmatter block refuses", "no frontmatter" in msg, msg)
        check("H3: that refusal leaves git status unchanged", git_status(repo) == before_status)

    # H3: an untracked todo refuses cleanly in phase 1 (never reaches git mv).
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "todos/archive/.keep"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        (repo / "todos" / "561-pending-p3-x.md").write_text(simple_todo_text("561", None, None))
        before_status = git_status(repo)
        msg = raises(lambda: land.archive(repo, "todos/561-pending-p3-x.md", "r", "2026-09-27"))
        check("H3: an untracked todo refuses", "not tracked in git" in msg, msg)
        check("H3: that refusal leaves git status unchanged", git_status(repo) == before_status)

    # H3: a multi-line 'status' value (set_fields can't rewrite it in place) refuses.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        (repo / "todos" / "562-pending-p3-x.md").write_text(
            '---\nstatus: |\n  pending\n  weird\nissue_id: "562"\n---\n\n# T\n\n'
            "## Acceptance Criteria\n\n- [x] a\n\n## Work Log\n\n### d - created\n\n## Notes\n\nn\n")
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "todos"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        before_status = git_status(repo)
        msg = raises(lambda: land.archive(repo, "todos/562-pending-p3-x.md", "r", "2026-09-27"))
        check("H3: a multi-line 'status' value refuses", "multi-line" in msg, msg)
        check("H3: that refusal leaves git status unchanged", git_status(repo) == before_status)

    # H3: a multi-line 'source_review' value refuses too -- only checked when a rename
    # is actually planned (this fixture's only finding closes the section), since
    # that's the only path that would later call set_fields(source_review=...).
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "docs" / "reviews").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        (repo / "todos" / "593-pending-p3-x.md").write_text(
            '---\nstatus: pending\npriority: p3\nissue_id: "593"\ndependencies: []\n'
            'source_review: >-\n  docs/reviews/h3d.md\nsource_finding: "1"\n---\n\n# T\n\n'
            "## Acceptance Criteria\n\n- [x] a\n\n## Work Log\n\n### d - created\n\n## Notes\n\nn\n")
        (repo / "docs/reviews/h3d.md").write_text("# R\n\n## Finding Status\n\n- [ ] #1 x → todo 593\n")
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        before_status = git_status(repo)
        msg = raises(lambda: land.archive(repo, "todos/593-pending-p3-x.md", "r", "2026-09-27"))
        check("H3: a multi-line 'source_review' value refuses when a rename is planned",
              "source_review" in msg and "multi-line" in msg, msg)
        check("H3: that refusal leaves git status unchanged", git_status(repo) == before_status)

    # H3: a missing 'todos/archive/' directory refuses cleanly in phase 1.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos").mkdir(parents=True)
        (repo / "todos" / "563-pending-p3-x.md").write_text(simple_todo_text("563", None, None))
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "todos"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        before_status = git_status(repo)
        msg = raises(lambda: land.archive(repo, "todos/563-pending-p3-x.md", "r", "2026-09-27"))
        check("H3: a missing todos/archive/ directory refuses", "does not exist" in msg, msg)
        check("H3: that refusal leaves git status unchanged", git_status(repo) == before_status)

    # H4: a lone fence-toggling line (``` or ~~~) in a quoted evidence tail must not
    # hide a REAL unchecked box elsewhere in the file from the archive gate.
    for fence in ("~~~", "```"):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            (repo / "todos" / "archive").mkdir(parents=True)
            (repo / "todos" / "archive" / ".keep").write_text("")
            (repo / "todos" / "570-pending-p3-x.md").write_text(
                '---\nstatus: pending\npriority: p3\nissue_id: "570"\ndependencies: []\n---\n\n# T\n\n'
                "## Acceptance Criteria\n\n- [ ] a\n\n## Work Log\n\n### d - created\n\n"
                "## Notes\n\n- [ ] real open sub-task\n")
            (repo / ".sweep-evidence/g").mkdir(parents=True)
            (repo / ".sweep-evidence/g/e.txt").write_text(f"ok\n{fence}\nend\n")
            subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "add", "todos"], check=True)
            subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m",
                            "x"], check=True)
            land.flip_acs(repo, "todos/570-pending-p3-x.md",
                          [{"todo": "570", "index": 0, "text": "a", "command": "pytest",
                            "evidence_path": ".sweep-evidence/g/e.txt", "pass": True}],
                          [{"todo": "570", "index": 0, "verified": True}], "r", "2026-09-27")
            msg = raises(lambda: land.archive(repo, "todos/570-pending-p3-x.md", "r", "2026-09-27"))
            check(f"H4: a lone {fence!r} line in a quoted tail doesn't hide a real bare box",
                  "unchecked criteria" in msg, msg)

    # H5/G1: a real flip (with a Verified note for THIS run) DOES claim "evidence is
    # quoted above" -- the positive-path mutation-survival gap from round 2.
    with tempfile.TemporaryDirectory() as tmp:
        repo = setup(tmp)
        rel = "todos/412-pending-p3-a.md"
        (repo / ".sweep-evidence/g1/412-ac3.txt").write_text("ok\n")
        land.flip_acs(repo, rel, [entry("412", 0), entry("412", 1), entry("412", 2)],
                      [agree("412", 0), agree("412", 1), agree("412", 2)], "r", "2026-09-27")
        result = land.archive(repo, rel, "r", "2026-09-27")
        note = (repo / result["archived"]).read_text()
        check("H5/G1: a real flip claims 'evidence is quoted above'", "evidence is quoted above" in note, note)

    # H5/G1: the claim is tied to THIS run_id -- a Verified note from a different run
    # (however real) does not count.
    with tempfile.TemporaryDirectory() as tmp:
        repo = setup(tmp)
        rel = "todos/412-pending-p3-a.md"
        (repo / ".sweep-evidence/g1/412-ac3.txt").write_text("ok\n")
        land.flip_acs(repo, rel, [entry("412", 0), entry("412", 1), entry("412", 2)],
                      [agree("412", 0), agree("412", 1), agree("412", 2)], "other-run", "2026-09-27")
        result = land.archive(repo, rel, "this-run", "2026-09-27")
        note = (repo / result["archived"]).read_text()
        check("H5/G1: a Verified note from a DIFFERENT run_id does not count",
              "evidence is quoted above" not in note, note)

    # H5/G4: a non-.md path gives a no-op note (is_file kept -- see the directory case
    # right after, which needs is_file specifically, not merely 'exists').
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "docs" / "reviews").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        (repo / "todos" / "580-pending-p3-x.md").write_text(simple_todo_text("580", "docs/reviews/r.txt", "1"))
        (repo / "docs/reviews/r.txt").write_text("not markdown\n")
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        result = land.archive(repo, "todos/580-pending-p3-x.md", "r", "2026-09-27")
        check("H5/G4: a non-.md path is a no-op, not a review doc",
              result["review"]["note"] == "source_review is not a review doc: docs/reviews/r.txt", result)

    # H5/G4: a directory sitting where the review doc would be is a no-op, not read
    # as if it were the file -- is_file() must stay, not loosen to exists().
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "docs" / "reviews").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        (repo / "todos" / "581-pending-p3-x.md").write_text(simple_todo_text("581", "docs/reviews/r.md", "1"))
        (repo / "docs/reviews/r.md").mkdir()
        (repo / "docs/reviews/r.md/keep").write_text("k")
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        result = land.archive(repo, "todos/581-pending-p3-x.md", "r", "2026-09-27")
        check("H5/G4: a directory named like the review doc is a no-op",
              result["review"]["note"] == "source_review is not a review doc: docs/reviews/r.md", result)

    # H5/G5: an evidence_path itself (not just `command`) containing an embedded
    # newline + heading is sanitized when quoted, not injected -- and the flip that
    # legitimately resolves to a file with that literal name still succeeds.
    with tempfile.TemporaryDirectory() as tmp:
        repo = setup(tmp)
        rel = "todos/412-pending-p3-a.md"
        (repo / ".sweep-evidence/g1/412-ac3.txt").write_text("ok\n")
        weird_name = "412-ac1b.txt\n## injected"
        (repo / ".sweep-evidence/g1" / weird_name).write_text("ok\n")
        mal = entry("412", 0)
        mal["evidence_path"] = f".sweep-evidence/g1/{weird_name}"
        flipped, left = land.flip_acs(repo, rel, [mal, entry("412", 1), entry("412", 2)],
                                      [agree("412", 0), agree("412", 1), agree("412", 2)], "r", "2026-09-27")
        text = (repo / rel).read_text()
        check("H5/G5: a flip with a newline-bearing evidence_path still succeeds", flipped == [0, 1, 2], flipped)
        check("H5/G5: an evidence_path containing a newline+heading is sanitized, not injected",
              sum(1 for line in text.splitlines() if line.startswith("## ")) == 3, text)
        check("H5/G5: the sanitized evidence_path still appears, flattened to one line",
              ".sweep-evidence/g1/412-ac1b.txt ## injected" in text, text)

    # H5/G7: checked-first, open-second, BOTH targeting this todo -- the open line
    # gets checked off (the simplest duplicate case, straight from the ruling text).
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "docs" / "reviews").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        (repo / "todos" / "590-pending-p3-x.md").write_text(simple_todo_text("590", "docs/reviews/g7c.md", "1"))
        (repo / "docs/reviews/g7c.md").write_text(
            "# R\n\n## Finding Status\n\n- [x] #1 a → todo 590 (completed 2026-01-01)\n- [ ] #1 b → todo 590\n")
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        result = land.archive(repo, "todos/590-pending-p3-x.md", "r", "2026-09-27")
        g7c = (repo / "docs/reviews/g7c-COMPLETED.md").read_text()
        check("H5/G7: checked-first, open-second (both target this todo) -- the open line is checked off",
              "- [x] #1 b → todo 590 (completed 2026-09-27)" in g7c, g7c)
        check("H5/G7: both lines end up checked, so the review doc renames",
              result["review"]["renamed"] is True, result)

    # H5/G7 behaviour: several OPEN lines for this finding that all target this todo
    # ship together -- they are the same finding, not independent duplicates.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "docs" / "reviews").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        (repo / "todos" / "591-pending-p3-x.md").write_text(simple_todo_text("591", "docs/reviews/g7d.md", "1"))
        (repo / "docs/reviews/g7d.md").write_text(
            "# R\n\n## Finding Status\n\n- [ ] #1 a → todo 591\n- [ ] #1 b → todo 591\n")
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        result = land.archive(repo, "todos/591-pending-p3-x.md", "r", "2026-09-27")
        g7d = (repo / "docs/reviews/g7d-COMPLETED.md").read_text()
        check("H5/G7: several open lines all targeting this todo are ALL checked off together",
              "- [x] #1 a → todo 591 (completed 2026-09-27)" in g7d
              and "- [x] #1 b → todo 591 (completed 2026-09-27)" in g7d, g7d)
        check("H5/G7: checking off both closes the section, so it renames",
              result["review"]["renamed"] is True, result)

    # H5/G7 note fallback: an open line for someone ELSE listed FIRST, this todo's own
    # already-checked line SECOND -- must still read "already checked" (probe's "dup h").
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "docs" / "reviews").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        (repo / "todos" / "592-pending-p3-x.md").write_text(simple_todo_text("592", "docs/reviews/g7e.md", "1"))
        (repo / "docs/reviews/g7e.md").write_text(
            "# R\n\n## Finding Status\n\n- [ ] #1 a → todo 999 (re-pointed 2026-01-01)\n"
            "- [x] #1 b → todo 592 (completed 2026-01-01)\n")
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        result = land.archive(repo, "todos/592-pending-p3-x.md", "r", "2026-09-27")
        check("H5/G7: an open-other-target line FIRST, this todo's checked line SECOND "
              "-- still reads 'already checked'",
              result["review"]["note"] == "already checked", result)
        check("H5/G7: the open-other-target line is untouched",
              "- [ ] #1 a → todo 999" in (repo / "docs/reviews/g7e.md").read_text())

    # Fix round 4, finding 1: a directory or a dangling symlink at the todo's own
    # archive destination refuses in PHASE 1. A recording git= callback proves no
    # phase-2 write started (a dangling symlink also fails the unfixed code's git mv
    # with a LandError, so "LandError + status unchanged" alone can't tell them apart).
    def dest_blocker_case(label, make_blocker):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            (repo / "todos" / "archive").mkdir(parents=True)
            (repo / "todos" / "archive" / ".keep").write_text("")
            (repo / "todos" / "600-pending-p3-x.md").write_text(simple_todo_text("600", None, None))
            subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "add", "todos"], check=True)
            subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit",
                            "-q", "-m", "x"], check=True)
            make_blocker(repo / "todos" / "archive" / "600-completed-p3-x.md")
            before_status = git_status(repo)
            calls = []

            def recording_git(repo_arg, *args):
                calls.append(args)
                return land.run_git(repo_arg, *args)

            try:
                msg = raises(lambda: land.archive(repo, "todos/600-pending-p3-x.md", "r", "2026-09-27",
                                                  git=recording_git))
            except Exception as exc:  # the unfixed code dies with IsADirectoryError here
                msg = f"UNEXPECTED {type(exc).__name__}: {exc}"
            check(f"R4/1: a {label} at the archive destination refuses in phase 1",
                  "destination already exists: todos/archive/600-completed-p3-x.md" in msg, msg)
            check(f"R4/1: the {label} refusal made no git call (phase 2 never started)", calls == [], calls)
            check(f"R4/1: the {label} refusal leaves git status unchanged", git_status(repo) == before_status,
                  git_status(repo))
            check(f"R4/1: the {label} refusal leaves the todo in place",
                  (repo / "todos" / "600-pending-p3-x.md").is_file())

    def make_dir(path):
        path.mkdir()
        (path / "keep.txt").write_text("k\n")

    dest_blocker_case("directory", make_dir)
    dest_blocker_case("dangling symlink", lambda path: os.symlink("nowhere.md", path))

    # Fix round 4, finding 2: a -COMPLETED twin git still tracks but that was deleted
    # from disk (os.remove, not git rm) is "already there" -- skip the rename, and
    # leave the twin's index entry byte-identical.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "docs" / "reviews").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        (repo / "todos" / "601-pending-p3-x.md").write_text(simple_todo_text("601", "docs/reviews/r4b.md", "1"))
        (repo / "docs/reviews/r4b.md").write_text("# R\n\n## Finding Status\n\n- [ ] #1 x → todo 601\n")
        (repo / "docs/reviews/r4b-COMPLETED.md").write_text("# an older, already-completed twin\n")
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        os.remove(repo / "docs/reviews/r4b-COMPLETED.md")

        def twin_stage():
            return subprocess.run(["git", "-C", str(repo), "ls-files", "--stage", "docs/reviews/r4b-COMPLETED.md"],
                                  capture_output=True, text=True).stdout

        before_stage = twin_stage()
        try:
            result = land.archive(repo, "todos/601-pending-p3-x.md", "r", "2026-09-27")
        except Exception as exc:
            result = {"review": {"renamed": None, "note": f"UNEXPECTED {type(exc).__name__}: {exc}"}}
        check("R4/2: a tracked-but-deleted twin skips the rename with the skip note",
              result["review"]["renamed"] is False
              and result["review"]["note"] == "all findings resolved, but docs/reviews/r4b-COMPLETED.md "
                                              "already exists; rename skipped", result)
        check("R4/2: the twin's index entry is byte-identical", before_stage != "" and twin_stage() == before_stage,
              (before_stage, twin_stage()))
        check("R4/2: the review doc was checked off in place",
              "- [x] #1 x → todo 601 (completed 2026-09-27)" in (repo / "docs/reviews/r4b.md").read_text())
        check("R4/2: the todo itself still archived",
              (repo / "todos/archive/601-completed-p3-x.md").is_file())

    # Fix round 4, finding 3: malformed YAML frontmatter -> the CLI exits 2 with a
    # `land: ` message, not a traceback (yaml.YAMLError is not a ValueError).
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        (repo / "todos" / "602-pending-p3-x.md").write_text(
            '---\nstatus: [unclosed\nissue_id: "602"\n---\n\n# T\n\n## Acceptance Criteria\n\n- [x] a\n\n'
            "## Work Log\n\n### d - created\n\n## Notes\n\nn\n")
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "todos"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "x"],
                       check=True)
        run_file = Path(tmp) / "run.json"
        run_file.write_text(json.dumps({"run_id": "r", "todos": {"602": {"path": "todos/602-pending-p3-x.md"}}}))
        before_status = git_status(repo)
        land_py = Path(os.path.abspath(__file__)).parent / "land.py"
        proc = subprocess.run([sys.executable, str(land_py), "archive", "--run", str(run_file), "--id", "602",
                               "--repo", str(repo), "--date", "2026-09-27"], capture_output=True, text=True)
        check("R4/3: malformed frontmatter exits 2", proc.returncode == 2, (proc.returncode, proc.stderr))
        check("R4/3: with a `land: ` message, not a traceback",
              proc.stderr.startswith("land: ") and "Traceback" not in proc.stderr, proc.stderr)
        check("R4/3: and nothing was written", git_status(repo) == before_status, git_status(repo))

    # Final review C1: a criterion wrapped onto an indented continuation line (29 of 47
    # open todos at origin/main) is matched on its WHOLE text. The body is verbatim from
    # origin/main:todos/467-pending-p3-delete-ai-care-service-and-diagnosis-count-race.md.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / "repo"
        (repo / "todos" / "archive").mkdir(parents=True)
        (repo / "todos" / "archive" / ".keep").write_text("")
        rel = "todos/467-pending-p3-x.md"
        (repo / rel).write_text(
            '---\nstatus: pending\npriority: p3\nissue_id: "467"\ndependencies: []\n---\n\n# T\n\n'
            "## Acceptance Criteria\n\n"
            "- [ ] `ai_care_service.py` is deleted, and the architecture doc's tree no\n"
            "      longer lists it; the full backend suite passes.\n"
            "- [ ] `diagnosis_count` is incremented with `F()`, with a test that fails on\n"
            "      the read-modify-write version.\n"
            "- [ ] The other read-modify-write counters are listed with a keep or fix\n"
            "      verdict each.\n"
            "\n```markdown\n- [ ] fenced example that\n      wraps\n```\n\n## Work Log\n\n### d - created\n\n")
        whole = ["`ai_care_service.py` is deleted, and the architecture doc's tree no longer lists it; "
                 "the full backend suite passes.",
                 "`diagnosis_count` is incremented with `F()`, with a test that fails on the read-modify-write "
                 "version.",
                 "The other read-modify-write counters are listed with a keep or fix verdict each."]
        ev = repo / ".sweep-evidence" / "g1"
        ev.mkdir(parents=True)
        entries = []
        for n, text in enumerate(whole):
            (ev / f"467-ac{n}.txt").write_text("ok\n")
            entries.append({"todo": "467", "index": n, "text": text, "command": f"c{n}",
                            "evidence_path": f".sweep-evidence/g1/467-ac{n}.txt", "pass": True})
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "todos"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q",
                        "-m", "x"], check=True)
        before = (repo / rel).read_text()
        first_only = [dict(e, text=e["text"].split(" longer")[0]) if e["index"] == 0 else e for e in entries]
        msg = raises(lambda: land.flip_acs(repo, rel, first_only, [agree("467", n) for n in range(3)], "r", "d"))
        check("C1: ac.json text holding only the first physical line of a wrapped criterion refuses",
              "does not match" in msg and (repo / rel).read_text() == before, msg)
        try:
            flipped, left = land.flip_acs(repo, rel, entries, [agree("467", n) for n in range(3)], "r", "d")
            err = None
        except land.LandError as exc:
            flipped, left, err = [], [], exc
        text = (repo / rel).read_text()
        check("C1: ac.json text holding the whole wrapped bullet flips every criterion",
              err is None and flipped == [0, 1, 2] and left == [], err or (flipped, left))
        check("C1: the flip edits only the checkbox line; the continuation stays put",
              "- [x] `ai_care_service.py` is deleted, and the architecture doc's tree no\n"
              "      longer lists it;" in text, text)
        check("C1: the fenced wrapped example is still not a criterion", "- [ ] fenced example that" in text)
        check("C1: the CI tripwire sees no bare box once the wrapped criteria are flipped",
              check_archived_todo_status.parse(str(repo / rel))[3] == [])
        try:
            result = land.archive(repo, rel, "r", "d")
        except land.LandError as exc:
            result = {"error": str(exc)}
        check("C1: the flipped wrapped todo archives",
              result.get("archived") == "todos/archive/467-completed-p3-x.md", result)

    # Final review m5: an evidence tail that echoes a .env value (repo or MAIN_ROOT,
    # backend/ or web/) is masked before it is quoted into the committed Work Log.
    with tempfile.TemporaryDirectory() as tmp:
        repo = setup(tmp)
        main_root = Path(tmp) / "main"
        (main_root / "web").mkdir(parents=True)
        (repo / "backend").mkdir()
        (repo / "backend" / ".env").write_text(
            "SECRET_KEY='repo-secret-value-xyz'\nDEBUG=True\nSHORT=abc1234\n")  # pragma: allowlist secret (fake)
        (main_root / "web" / ".env").write_text("export VITE_TOKEN=\"main-web-token-123\"\n")
        (repo / ".sweep-evidence/g1/412-ac1.txt").write_text(
            "SECRET_KEY=repo-secret-value-xyz\nurl https://x/?t=main-web-token-123\nSHORT=abc1234 DEBUG=True\n")
        leaky = dict(entry("412", 0), command="curl -H 'X-Token: main-web-token-123' https://x/health")
        land.flip_acs(repo, "todos/412-pending-p3-a.md", [leaky] + [entry("412", i) for i in (1, 2)],
                      [agree("412", 0)], "r", "2026-09-27", main_root=str(main_root))
        text = (repo / "todos/412-pending-p3-a.md").read_text()
        check("m5: a backend/.env value in the repo is masked in the quoted tail",
              "repo-secret-value-xyz" not in text and "SECRET_KEY=***" in text, text)
        check("m5: a web/.env value under MAIN_ROOT is masked too",
              "main-web-token-123" not in text and "?t=***" in text, text)
        check("m5: values shorter than 8 characters are left alone", "SHORT=abc1234 DEBUG=True" in text, text)
        check("m5 residual: a .env value in the AC command is masked before it is quoted",
              "`curl -H 'X-Token: ***' https://x/health`" in text, text)

    # Todo 468 m5 residuals: a DATABASE_URL password printed on its own, a slotted URL whose DB name
    # is not the local one, and one secret inside another (the longest-first order is what masks it).
    with tempfile.TemporaryDirectory() as tmp:
        repo = setup(tmp)
        (repo / "backend").mkdir()
        (repo / "backend" / ".env").write_text(  # fake values, test fixture only
            "DATABASE_URL=postgresql://plant:S3cretPassw0rd@localhost:5432/mydb\n"  # pragma: allowlist secret
            "TOKEN_SHORT=abcdefgh\nTOKEN_LONG=abcdefgh12345678\n")  # pragma: allowlist secret
        (repo / ".sweep-evidence/g1/412-ac1.txt").write_text(
            "connecting with password S3cretPassw0rd\n"  # pragma: allowlist secret
            "DATABASE_URL=postgresql://plant:S3cretPassw0rd@%2Ftmp:5432/plant_community_w3\n"  # pragma: allowlist secret
            "token abcdefgh12345678 ok\n")  # pragma: allowlist secret
        land.flip_acs(repo, "todos/412-pending-p3-a.md", [entry("412", i) for i in range(3)],
                      [agree("412", 0)], "r", "2026-09-28")
        text = (repo / "todos/412-pending-p3-a.md").read_text()
        check("468: a DATABASE_URL password printed on its own is masked",
              "S3cretPassw0rd" not in text and "connecting with password ***" in text, text)
        check("468: a slotted DATABASE_URL is masked whatever the local DB name",
              "postgresql://plant:***@%2Ftmp:5432/plant_community_w3" in text, text)
        check("468: a secret containing a shorter secret is masked whole (longest first)",
              "12345678" not in text and "token *** ok" in text, text)

    # Final review m9: no Work Log heading a worker is told to write may satisfy Land's
    # "evidence is quoted above" check -- only flip_acs's own heading does.
    worker_md = (Path(os.path.abspath(__file__)).parents[2] / ".claude" / "agents" / "todo-worker.md").read_text()
    section = worker_md.split("## Work Log", 1)[1].split("\n## ", 1)[0]
    headings = re.findall(r'"([A-Z][a-z]+ by)"', section)
    check("m9: the worker names its three Work Log headings", len(headings) >= 3, headings)
    check("m9: the verify-only heading is 'Checked by'", "Checked by" in headings, headings)
    colliding = [h for h in headings
                 if land.has_verified_note_for(f"### d - {h} the todo sweep (run r1)\n", "r1")
                 and not re.search(rf"Never write \"{h}\"", section)]
    check("m9: no worker Work Log heading satisfies Land's Verified-note check", colliding == [], colliding)
    check("m9: flip_acs's own heading still does",
          land.has_verified_note_for("### d - Verified by the todo sweep (run r1)\n", "r1"))

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s): {', '.join(FAILURES)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
