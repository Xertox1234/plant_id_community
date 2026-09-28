#!/usr/bin/env python3
"""Tests for scripts/todos/todofile.py.

Run: python3 scripts/todos/test_todofile.py (also run by harness-ci.yml).

The cases that matter are the silent corruptions: a value YAML reinterprets
(`yes` -> True), a multi-line value half-rewritten, a checkbox inside a fenced
example counted as a criterion, and a Work Log entry landing under Notes.
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import todofile as tf  # noqa: E402

FAILURES = []


def check(label, condition, detail=""):
    print(f"  {'PASS' if condition else 'FAIL'}  {label}{'' if condition else f'  -- {detail}'}")
    if not condition:
        FAILURES.append(label)


HEAD = '---\nstatus: pending\npriority: p3\nissue_id: "412"\ntags: [web, forum]\ndependencies: []\n---\n'
BODY = (
    "\n# Onboarding checklist\n\n## Acceptance Criteria\n\n- [ ] first\n- [x] second\n\n"
    "```markdown\n- [ ] example inside a fence\n```\n\n"
    "- [ ] third -> todo 283 (re-pointed 2026-07-26)\n\n"
    "## Work Log\n\n### 2026-09-01 - Created\n\n- filed.\n\n## Notes\n\nnote text\n"
)


def write(tmp, text, name="412-pending-p3-x.md"):
    path = Path(tmp) / name
    path.write_text(text)
    return path


def main():
    with tempfile.TemporaryDirectory() as tmp:
        p = write(tmp, HEAD + BODY)
        data = tf.read_frontmatter(p)
        check("reads scalars and flow lists", data["issue_id"] == "412" and data["tags"] == ["web", "forum"], data)

        tf.set_fields(p, {"triage": "blocked-owner", "triaged": "2026-09-27"})
        text = p.read_text()
        check("appends new keys inside the block",
              "dependencies: []\ntriage: blocked-owner\ntriaged: 2026-09-27\n---\n" in text, text[:200])
        check("keeps the body byte for byte", text.endswith(BODY), text[-80:])

        tf.set_fields(p, {"triage": "ready"})
        check("replaces an existing key in place",
              tf.read_frontmatter(p)["triage"] == "ready" and p.read_text().count("\ntriage:") == 1)
        check("'triage' does not match the 'triaged' line", "triaged: 2026-09-27" in p.read_text())

        # Review focus 1: every value comes back as the same string.
        for value in ["yes", "412", "null", "a: b", 'say "hi"', "line1\nline2", ""]:
            tf.set_fields(p, {"owner_decision": value})
            got = tf.read_frontmatter(p)["owner_decision"]
            check(f"round-trips {value!r} as a string", got == value, repr(got))

        tf.set_fields(p, {"triaged": "2026-09-27"})
        check("ISO dates read back as datetime.date; str() gives the original text",
              str(tf.read_frontmatter(p)["triaged"]) == "2026-09-27")

        multi = write(tmp, "---\nstatus: pending\nblocked_on:\n  - a\n  - b\n---\n# t\n", "413-pending-p3-y.md")
        before = multi.read_text()
        try:
            tf.set_fields(multi, {"blocked_on": "x"})
            raised = False
        except ValueError:
            raised = True
        check("refuses a multi-line value and leaves the file alone", raised and multi.read_text() == before)

        check("no frontmatter reads as None", tf.read_frontmatter(write(tmp, "# prose\n", "old.md")) is None)
        comment = write(tmp, "---\nstatus: in_progress  # Change from pending\n---\n# t\n", "414-in_progress-p3-z.md")
        check("a YAML comment is not part of the value", tf.read_frontmatter(comment)["status"] == "in_progress")

        check("title is the first H1", tf.title(p.read_text()) == "Onboarding checklist")

        boxes = tf.ac_lines(p.read_text())
        check("ac_lines skips fenced examples", len(boxes) == 3, boxes)
        check("ac_lines reports checked state", [b[1] for b in boxes] == [False, True, False], boxes)
        check("is_repoint accepts the arrow convention", tf.is_repoint(boxes[2][2]))
        check("is_repoint rejects plain prose", not tf.is_repoint("- [ ] see todo notes"))

        tf.append_work_log(p, "### 2026-09-27 - Verified\n\n- ok.\n")
        text = p.read_text()
        check("work log entry lands before ## Notes",
              text.index("### 2026-09-27 - Verified") < text.index("## Notes")
              and text.index("### 2026-09-01 - Created") < text.index("### 2026-09-27 - Verified"), text)
        nolog = write(tmp, "---\nstatus: pending\n---\n# t\n", "415-pending-p3-w.md")
        tf.append_work_log(nolog, "### d - e\n")
        check("a missing Work Log section is created", nolog.read_text().endswith("## Work Log\n\n### d - e\n"))

        check("with_status swaps the status segment",
              tf.with_status("412-pending-p3-onboarding.md", "completed") == "412-completed-p3-onboarding.md")
        check("with_status keeps a date prefix",
              tf.with_status("2025-11-01-003-in_progress-p1-x.md", "pending") == "2025-11-01-003-pending-p1-x.md")
        try:
            tf.with_status("README.md", "completed")
            raised = False
        except ValueError:
            raised = True
        check("with_status refuses a name without a status segment", raised)
        check("archived_path swaps only the status segment and moves under todos/archive/",
              tf.archived_path("todos/412-pending-p2-some-name.md") == "todos/archive/412-completed-p2-some-name.md")

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} check(s): {', '.join(FAILURES)}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
