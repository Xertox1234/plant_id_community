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


WRAPPED_BODY = (
    "\n# Delete the orphaned `ai_care_service.py`\n\n## Acceptance Criteria\n\n"
    "- [ ] `ai_care_service.py` is deleted, and the architecture doc's tree no\n"
    "      longer lists it; the full backend suite passes.\n"
    "- [ ] `diagnosis_count` is incremented with `F()`, with a test that fails on\n"
    "      the read-modify-write version.\n"
    "\n```markdown\n- [ ] an example criterion inside a fence that\n      wraps onto a second line\n```\n\n"
    "- [ ] The other read-modify-write counters are listed with a keep or fix\n"
    "      verdict each.\n"
    "\nnot part of any criterion\n\n## Work Log\n\n### 2026-09-27 - Created\n\n- filed.\n"
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

        # Todo 475: YAML allows blanks before the colon. `key : value` is that key, so it is
        # rewritten in place -- a plain `key:` prefix match appended a duplicate line instead.
        spaced = write(tmp, '---\nstatus : pending\nsource_review :  "docs/reviews/a.md"\n'
                            'source_reviewer: x\n---\n# t\n', "415-pending-p3-s.md")
        tf.set_fields(spaced, {"status": "completed", "source_review": "docs/reviews/a-COMPLETED.md"})
        text = spaced.read_text()
        check("475: a `key : value` line is rewritten in place, not duplicated",
              text.count("status") == 1 and text.count("source_review:") == 1 and text.count("source_review ") == 0
              and tf.read_frontmatter(spaced)["status"] == "completed"
              and tf.read_frontmatter(spaced)["source_review"] == "docs/reviews/a-COMPLETED.md", text)
        check("475: a longer key sharing the prefix is not matched", "source_reviewer: x\n" in text, text)
        quoted = write(tmp, '---\n"status": pending\n---\n# t\n', "416-pending-p3-q.md")
        before = quoted.read_text()
        try:
            tf.set_fields(quoted, {"status": "completed"})
            raised = ""
        except ValueError as exc:
            raised = str(exc)
        check("475: a key set on a line it cannot find refuses and leaves the file alone",
              "cannot rewrite" in raised and quoted.read_text() == before, raised)
        check("475: field_problem is None for an absent key (set_fields appends it)",
              tf.field_problem(before, "triage") is None)

        # Todo 506: set_fields must refuse -- writing nothing -- whenever the rewrite would
        # leave frontmatter that reads differently, and must not refuse a key it can set.
        def refusal(name, frontmatter):
            path = write(tmp, f"---\n{frontmatter}---\n# t\n", name)
            before = path.read_text()
            try:
                tf.set_fields(path, {"source_review": "docs/reviews/a-COMPLETED.md"})
                return "", path.read_text() == before
            except ValueError as exc:
                return str(exc), path.read_text() == before

        for label, frontmatter in [("a blank line", 'source_review:\n\n  "docs/reviews/a.md"\n'),
                                   ("a comment line", 'source_review:\n# moved\n  "docs/reviews/a.md"\n')]:
            raised, untouched = refusal("417-pending-p3-m.md", "status: pending\n" + frontmatter)
            check(f"506 #1: a value after {label} is multi-line; refused, file untouched",
                  "multi-line" in raised and untouched, raised)
        raised, untouched = refusal("418-pending-p3-b.md", 'source_review: "docs/reviews/a.md"\n\nstatus: pending\n')
        check("506 #1: a blank line before the next key is not a multi-line value", raised == "", raised)
        text = (Path(tmp) / "418-pending-p3-b.md").read_text()
        check("519 #9: ... and set_fields rewrote the key line and nothing else",
              text == '---\nsource_review: "docs/reviews/a-COMPLETED.md"\n\nstatus: pending\n---\n# t\n', text)
        # Todo 519 #10: a comment line, then a top-level key, does not continue the value either. The key has an
        # indented value of its own, so a _next_content_line that skipped past the key would refuse here.
        raised, untouched = refusal("423-pending-p3-c.md", 'source_review: "a"\n# note\ntags:\n  - x\n')
        text = (Path(tmp) / "423-pending-p3-c.md").read_text()
        check("519 #10: a comment line before the next key is not a multi-line value; only the key line changes",
              raised == ""
              and text == '---\nsource_review: "docs/reviews/a-COMPLETED.md"\n# note\ntags:\n  - x\n---\n# t\n',
              raised or text)
        # Todo 519 #11: inside a block scalar an indented '#' line is content, not a comment.
        raised, untouched = refusal("424-pending-p3-k.md", "source_review: |\n  # moved to x\nstatus: pending\n")
        check("519 #11: a block scalar whose body starts with an indented '#' line is multi-line; refused, untouched",
              "multi-line" in raised and untouched, raised)
        # Todo 519 #13: the other-keys comparison of the read-back probe. A quoted value carried onto a column-0
        # line is one value, `"a status: b"`. The trial rewrite parses, and the key takes the probe value, so
        # neither of the first two tests refuses; only the comparison sees `status` appear as a new key.
        raised, untouched = refusal("425-pending-p3-o.md", 'source_review: "a\nstatus: b"\nother: c\n')
        check("519 #13: a rewrite that would add another key is refused, file untouched",
              "cannot rewrite" in raised and untouched, raised)
        raised, untouched = refusal("419-pending-p3-d.md", "source_review : a\nsource_review: b\n")
        check("506 #11: a key on two lines is refused, file untouched (YAML keeps the last one)",
              "more than one line" in raised and untouched, raised)
        raised, untouched = refusal("420-pending-p3-d.md", 'source_review: a\n"source_review": b\n')
        check("506 #12: a later quoted duplicate that would still win is refused, file untouched",
              "cannot rewrite" in raised and untouched, raised)
        raised, untouched = refusal("421-pending-p3-a.md", "source_review: &r a\nalso: *r\n")
        check("506 #1: a rewrite that would change another key (here an alias) is refused, file untouched",
              "cannot rewrite" in raised and untouched, raised)
        bad_date = write(tmp, "---\ncreated: 2026-02-30\nstatus: pending\n---\n# t\n", "422-pending-p3-v.md")
        try:
            tf.set_fields(bad_date, {"triage": "ready"})
            raised = ""
        except ValueError as exc:
            raised = str(exc)
        check("506 #13: an impossible date elsewhere keeps the append behaviour, not a ValueError",
              raised == ""
              and bad_date.read_text().startswith("---\ncreated: 2026-02-30\nstatus: pending\ntriage: ready\n"),
              raised or bad_date.read_text())

        check("no frontmatter reads as None", tf.read_frontmatter(write(tmp, "# prose\n", "old.md")) is None)
        comment = write(tmp, "---\nstatus: in_progress  # Change from pending\n---\n# t\n", "414-in_progress-p3-z.md")
        check("a YAML comment is not part of the value", tf.read_frontmatter(comment)["status"] == "in_progress")

        check("title is the first H1", tf.title(p.read_text()) == "Onboarding checklist")

        boxes = tf.ac_lines(p.read_text())
        check("ac_lines skips fenced examples", len(boxes) == 3, boxes)
        check("ac_lines reports checked state", [b[1] for b in boxes] == [False, True, False], boxes)
        check("is_repoint accepts the arrow convention", tf.is_repoint(boxes[2][2]))
        check("is_repoint rejects plain prose", not tf.is_repoint("- [ ] see todo notes"))

        # Final review C1: a criterion wrapped onto indented continuation lines is ONE
        # criterion, and its text is the whole bullet. Taken verbatim from
        # origin/main:todos/467-pending-p3-delete-ai-care-service-and-diagnosis-count-race.md
        # (29 of the 47 open todos wrap like this), plus a wrapped example inside a fence.
        wrapped = write(tmp, HEAD + WRAPPED_BODY, "467-pending-p3-w.md")
        boxes = tf.ac_lines(wrapped.read_text())
        check("ac_lines counts a wrapped criterion once and skips the fenced one", len(boxes) == 3, boxes)
        check("ac_lines keeps line_no on the checkbox line",
              [wrapped.read_text().splitlines()[b[0]].lstrip().startswith("- [ ]") for b in boxes] == [True] * 3,
              boxes)
        check("ac_lines joins continuation lines with one space",
              boxes and boxes[0][2] == "- [ ] `ai_care_service.py` is deleted, and the architecture doc's tree no "
              "longer lists it; the full backend suite passes.", boxes[:1])
        check("ac_lines does not swallow the next bullet or a following paragraph",
              len(boxes) == 3 and boxes[2][2] == "- [ ] The other read-modify-write counters are listed with a keep "
              "or fix verdict each.", boxes[2:])

        # Todo 468 N2: a continuation line that starts with `#42` or `10.` is still text. A heading
        # needs #s then a space, and only `1.` can start a list inside a paragraph (CommonMark).
        n2 = write(tmp, HEAD + "\n# t\n\n## Acceptance Criteria\n\n"
                   "- [ ] The status line names the finding, as in finding\n"
                   "      #42 of the review, and the count is at most\n"
                   "      10. More text after it.\n"
                   "- [ ] Second criterion\n"
                   "  1. a real numbered sub-list\n"
                   "  ## a real heading\n", "468-pending-p3-n2.md")
        boxes = tf.ac_lines(n2.read_text())
        check("468 N2: a wrapped line starting with #42 or 10. stays part of its criterion",
              len(boxes) == 2 and boxes[0][2] == "- [ ] The status line names the finding, as in finding #42 of the "
              "review, and the count is at most 10. More text after it.", boxes)
        check("468 N2: a `1.` item and a real heading still end a criterion",
              len(boxes) == 2 and boxes[1][2] == "- [ ] Second criterion", boxes[1:])
        # Todo 468 N3: an indented fence right under a criterion must reach the fence toggle, or the
        # fenced example is read as a criterion and the real one after the fence is skipped.
        n3 = write(tmp, HEAD + "\n# t\n\n## Acceptance Criteria\n\n"
                   "- [ ] Criterion one\n"
                   "  ```markdown\n"
                   "  - [ ] an example, not a criterion\n"
                   "  ```\n"
                   "- [ ] Criterion two\n", "468-pending-p3-n3.md")
        boxes = tf.ac_lines(n3.read_text())
        check("468 N3: an indented fence under a criterion ends it, and the fenced example is skipped",
              [b[2] for b in boxes] == ["- [ ] Criterion one", "- [ ] Criterion two"], boxes)

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
