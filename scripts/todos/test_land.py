#!/usr/bin/env python3
"""Tests for scripts/todos/land.py.

Run: python3 scripts/todos/test_land.py (also run by harness-ci.yml).

land.py is where a checkbox becomes a claim. Pinned here: a box flips only
with the worker's pass AND the verifier's agreement AND an evidence file;
ac.json that disagrees with the todo stops everything; fenced examples are
not criteria; archive refuses bare boxes but accepts re-points; the review
doc is renamed COMPLETED only when nothing is left open.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import land  # noqa: E402
import todofile  # noqa: E402

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


def entry(todo, index, passed=True, evidence=True):
    return {"todo": todo, "index": index, "text": "t", "command": f"pytest ac{index + 1}",
            "evidence_path": f".sweep-evidence/g1/{todo}-ac{index + 1}.txt" if evidence else "", "pass": passed}


def agree(todo, index, ok=True):
    return {"todo": todo, "index": index, "verified": ok, "note": ""}


def raises(fn):
    try:
        fn()
    except land.LandError as exc:
        return str(exc)
    return ""


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

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s): {', '.join(FAILURES)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
