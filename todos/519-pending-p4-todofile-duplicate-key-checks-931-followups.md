---
status: pending
priority: p4
issue_id: "519"
tags: [tooling, todo-sweep]
dependencies: []
---

# Todofile duplicate-key checks: non-blocking findings from PR #931 (todo 506)

## Problem

PR #931 (todo 506) merged after two review rounds in todo-sweep run 2026-10-02-0118. The findings below were rated non-blocking, so they were not repaired. Findings at the same file:line are merged; each one says which round reported it. Line numbers are as of the PR head. Re-check each finding against main before acting on it.

## Findings

1. **`scripts/todos/land.py:453`** (low, round 2). \_SOURCE\_REVIEW\_LINE\_RE anchors `source_review` at column 0, so an unreadable sibling whose key is indented (a common cause of the YAML error) or sits in a flow mapping is no longer reported. Probed: the key indented by one space (`source_review: "docs/reviews/s.md"` with a leading blank) gives ScannerError and \_mentions False, so the pointer dangles silently.
   Suggested: Allow leading blanks and a flow-mapping position, e.g. `^(?:[ \t]*|.*[{,][ \t]*)(["']?)source_review\1[ \t]*:(.*)$`. Take continuation lines as those indented deeper than the key. Add an indented-key case to the 506 #2-#6 table.

2. **`scripts/todos/land.py:468`** (low, round 2). \_mentions matches the review's basename in any directory, and whitespace counts as a boundary. Probes return True for an unreadable sibling with `source_review: docs/reviews/archive/s.md` and for `.../o.md  # was s.md`, so each still gets a false 'still names' Work Log bullet. The dot-dot test passes only because the basename matches.
   Suggested: Strip a trailing `#...` comment from the joined value, then match the repo-relative review path after normalising (posixpath.normpath with a leading ./ removed). At minimum require `/` or a quote before the name. Add an other-directory case that expects False.
   Also reported: \_mentions' segment regex does not accept flow-list or comma delimiters (`[docs/reviews/s.md, x]`), so an unreadable sibling spelled that way is missed. It also matches the same basename in a different directory.

3. **`scripts/todos/land.py:476`** (low, round 1, round 2). \_mentions stops collecting a source\_review value at a column-0 comment line, but YAML (and field\_problem's new \_next\_content\_line) carries the value past it. An unreadable sibling with `source_review:\n# moved\n  "docs/reviews/s.md"` returns False, so its dangling pointer goes unreported. Verified in memory.
   Suggested: In the continuation loop, skip comment-only lines (`more.lstrip().startswith('#')`) as well as blank ones before breaking, the same way \_next\_content\_line does. Add that shape to the 506 #2-#6 cases.
   Also reported: \_mentions stops collecting a source\_review value at any column-0 non-blank line, including a comment. For an unreadable sibling with `source_review:`, then `# c`, then an indented review path (valid YAML, the finding-1 shape), it returns False. The old substring test caught it, so that sibling's pointer now dangles with no Work Log note.

4. **`scripts/todos/land.py:477`** (low, round 1). \_mentions segment match also fires on an inline YAML comment after the value (`source_review: "other.md" # was s.md`), a false sibling note. The test cases include no trailing-comment neighbour, so it is unpinned.
   Suggested: Strip `#...` comments from the value before matching, and add a trailing-comment case to the cases dict in test\_land.py.

5. **`scripts/todos/state.py:432`** (low, round 1). field\_problem now refuses more cases: duplicate key lines, and a rewrite that reads back differently. apply\_triage calls set\_fields mid-loop with no phase-1 field\_problem check, so these surface as a ValueError after earlier todos were already edited or git-mv'd. Pre-existing shape; a real-todo scan shows only archive/086 newly refused.
   Suggested: Optionally pre-check every target with todofile.field\_problem for each field before the write loop in apply\_triage, so a refusal happens before any write, matching land.archive's phase-1 pattern.

6. **`scripts/todos/test_land.py:1442`** (low, round 2). The \_mentions cases have no flow-list, comma-separated, or same-basename-in-another-directory specimen, so the delimiter set is not pinned from either side.
   Suggested: Add one case that should match (flow list) and one that should not (`docs/other/s.md`) to pin the intended rule.

7. **`scripts/todos/test_land.py:1468`** (low, round 1). The 506 #8 test only puts a line separator in `completed` and the sibling path. `source` ('s ### forged.md') has none, so dropping \_sanitize on plan['source'] would still pass. The Work Log also says U+2028/U+2029 are tested, but they are not in the test.
   Suggested: Put a separator in `source` too, e.g. 'docs/reviews/sU+2028## forged.md', and add the U+2028/U+2029 cases the Work Log claims. Or correct the Work Log bullet for finding 8.

8. **`scripts/todos/test_land.py:1469`** (low, round 2). The 506 #8 test puts literal U+2028 and U+2029 characters in the source. They are invisible to a reader (they look like spaces), and an editor or formatter could normalise them, which would quietly weaken the separator test.
   Suggested: Write them as `\u2028` and `\u2029` escapes, the way the next line already writes `\x85`.

9. **`scripts/todos/test_todofile.py:132`** (low, round 2). The positive-path check ('a blank line before the next key is not a multi-line value') asserts only that nothing was raised. It ignores what set\_fields wrote, so a corrupt rewrite would still pass.
   Suggested: Assert the file's text afterwards equals `---\nsource_review: "docs/reviews/a-COMPLETED.md"\n\nstatus: pending\n---\n# t\n`. The refusal helper could return the text, not just `untouched`.

10. **`scripts/todos/test_todofile.py:139`** (low, round 1). Pins a blank line before the next key, but not a comment-only line followed by a top-level key. If \_next\_content\_line stopped skipping comments, or skipped past a key, nothing would go red.
   Suggested: Add a refusal() case: `source_review: "a"\n# note\nstatus: pending\n` expecting no ValueError.

11. **`scripts/todos/todofile.py:94`** (low, round 1). \_next\_content\_line counts an indented '#' line as a comment, but inside a block scalar it is content. `source_review: |` followed by an indented `# moved to x` line used to be refused and now passes. set\_fields rewrites only the key line, so the old body stays behind as a stray YAML comment.
   Suggested: Skip only blank lines and column-0 comment lines, e.g. `line.strip() and not line.startswith('#')`, so any indented line, including an indented '#', still counts as a value continuation.

12. **`scripts/todos/todofile.py:101`** (low, round 2). The probe comment says set\_fields writes every value 'rendered quoted'. render() writes bare words (completed, ready) and ISO dates unquoted. The probe is still representative, since any one-line scalar works, but the comment is wrong.
   Suggested: Reword it to: 'a one-line scalar, like every value set\_fields writes'.

13. **`scripts/todos/todofile.py:107`** (low, round 1). No test reaches the 'any other key changed' comparison in field\_problem's read-back probe. The alias test (#1) refuses through the YAMLError path (after=None), and #12 through after.get(key) != probe. That branch may be practically unreachable defensive code.
   Suggested: Add a case that reaches the other-keys comparison without a parse error, or note in a comment that it is defensive only. Edits to existing tests are justified: test\_todofile.py changes one line (whitespace only, finding 10) and test\_land.py only adds checks.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-10-01: Filed from todo-sweep run 2026-10-02-0118, PR #931 review rounds 1-2.
