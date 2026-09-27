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
read (F6); Finding Status matching is indentation/case tolerant and an empty
Acceptance Criteria section refuses archive (F7); the archive Work Log entry
doesn't claim evidence that was never quoted (F8).
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

    # F1: a validation failure (destination already exists) leaves git status untouched.
    with tempfile.TemporaryDirectory() as tmp:
        repo = setup(tmp)
        rel = "todos/412-pending-p3-a.md"
        land.flip_acs(repo, rel, [entry("412", 0), entry("412", 1), entry("412", 2)],
                      [agree("412", 0), agree("412", 1), agree("412", 2)], "r", "2026-09-27")
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

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s): {', '.join(FAILURES)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
