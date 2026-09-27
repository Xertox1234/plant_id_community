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
just \\r and \\n (G5); a duplicate Finding Status line prefers the first OPEN
match, and source_review without source_finding is a no-op with a note, not a
silent skip (G7).
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

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s): {', '.join(FAILURES)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
