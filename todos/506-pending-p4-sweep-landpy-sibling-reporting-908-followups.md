---
status: pending
priority: p4
issue_id: "506"
tags: [tooling, todo-sweep]
dependencies: []
---

# Sweep land.py sibling reporting: non-blocking findings from PR #908 (todo 475)

## Problem

PR #908 (todo 475) merged after two review rounds in todo-sweep run 2026-10-01-0121. The findings below were rated non-blocking, so they were not repaired. Findings at the same file:line are merged; each one says which round reported it. Line numbers are as of the PR head. Re-check each finding against main before acting on it.

## Findings

1. **`scripts/todos/todofile.py:78`** (medium, round 1). field\_problem looks only at the line right after the key. With `source_review:` then a blank or `# c` line, then an indented value, it returns None. That value still resolves to the review, so set\_fields rewrites the key line and leaves the indented line orphaned; the frontmatter no longer parses (ParserError, reproduced in memory) and land stages it.
   Suggested: Skip blank and comment-only lines when finding the following line. Better: do the substitution in memory and re-parse, and return a problem if it fails to parse or any other key changes, so set\_fields never writes YAML it can't read back.

2. **`scripts/todos/land.py:441`** (low, round 2). In \_siblings, an unreadable sibling is reported only if its frontmatter text contains the review file name. An unparseable file that points at the review through a differently spelled path (./ or ../) is dropped silently, leaving its pointer dangling.
   Suggested: Match on the normalised path, or report any unreadable sibling whose frontmatter contains 'source\_review'.

3. **`scripts/todos/land.py:442`** (low, round 1). \_mentions matches the review doc's basename as a plain substring of the frontmatter. A todo with unparseable frontmatter that names e.g. 'notes.md' or 'x-\<review>.md' in any field is reported as a skipped sibling, which writes a false 'still names' bullet into the committed Work Log.
   Suggested: Match the name as a whole path component, e.g. re.search(rf'(^|/|\\s|")' + re.escape(name) + r'("|\\s|$)', fm, re.M), or require it on a line that starts with source\_review.

4. **`scripts/todos/land.py:444`** (low, round 2). \_mentions matches review.name as a plain substring of the frontmatter. A todo with unreadable frontmatter that mentions a longer name ending in the same text (for example `x-full-review.md` against `full-review.md`) is reported as a skipped sibling it is not. The cost is only an extra Work Log note.
   Suggested: Match the name as a whole path segment, e.g. re.search(rf'(?:^|[/\\s"\\']){re.escape(name)}(?:$|[\\s"\\'])', fm, re.M), or check for the repo-relative review path instead of the bare name.

5. **`scripts/todos/land.py:446`** (low, round 1). \_mentions matches review.name by bare substring in the frontmatter, so an unreadable todo naming a different doc whose name contains it (e.g. 's.md' in 'tests.md') yields a spurious skipped-sibling Work Log note.
   Suggested: Match the repo-relative review path or use a boundary-anchored regex instead of a bare file name.

6. **`scripts/todos/land.py:449`** (low, round 1, round 2). \_mentions does a raw substring test of review.name against the whole frontmatter. A sibling with unparseable YAML that names the doc in another field (or a longer name containing it) is reported as a sibling still pointing at the review, a false Work Log note.
   Suggested: Match only a source\_review line, e.g. re.search(rf'^"?source\_review"?[ \\t]*:.*{re.escape(name)}', fm, re.M), or require a path separator or quote right before the name.
   Also reported: \_mentions matches review.name as a plain substring of the frontmatter. An unreadable sibling naming e.g. docs/reviews/xs.md, or s.md.bak, counts as a sibling of s.md. archive() then writes a false 'still names \<review>' line into the committed Work Log.

7. **`scripts/todos/land.py:468`** (low, round 1). No test asserts the new apply\_review note suffix '; N sibling todo(s) not rewritten'. Also, renamed=False returns leave out the skipped\_siblings key, so callers see two different result shapes.
   Suggested: Add a check that review['note'] ends with '; 4 sibling todo(s) not rewritten' in the 475 test. Optionally return skipped\_siblings: [] on every path so the shape is always the same.

8. **`scripts/todos/land.py:533`** (low, round 1, round 2). The new Work Log bullets run path and reason through \_sanitize, but review\_plan['source'] and review\_plan['completed'] go in raw. A review doc whose file name has a line separator could forge a heading in the committed Work Log, which \_sanitize exists to stop.
   Suggested: Wrap review\_plan['source'] and review\_plan['completed'] in \_sanitize(), the same as s['path'] and s['reason'].
   Also reported: The new skipped-sibling Work Log bullet runs s['path'] and s['reason'] through \_sanitize, but review\_plan['source'] and review\_plan['completed'] are interpolated raw. A review-doc filename with a line separator could forge a heading in the committed record. Both are tracked paths under docs/reviews, so the exposure is small.
   Also reported: The Work Log line passes s['path'] and s['reason'] through \_sanitize, but interpolates review\_plan['source'] and review\_plan['completed'] raw. A review filename that contains a line separator could start a new line in the archived todo.
   Also reported: The new skipped-sibling Work Log line passes s['path'] and s['reason'] through \_sanitize, but review\_plan['source'] and review\_plan['completed'] go in raw. Both come from real file names under docs/reviews/. A review doc whose name contains a line separator could add a forged line or heading to the committed Work Log of a public repo.

9. **`scripts/todos/test_land.py:1372`** (low, round 2). Coverage gap: no test asserts that apply\_review appends `; N sibling todo(s) not rewritten` to review.note. That note is the part of the JSON output a Stage D reader sees, and dropping it would go unnoticed.
   Suggested: Add a check in the 475 block: `'4 sibling todo(s) not rewritten' in review['note']`.

10. **`scripts/todos/test_todofile.py:115`** (low, round 1, round 2). Of the flagged test edits, test\_land.py only adds lines and is justified. In test\_todofile.py the only changed existing line is `no frontmatter reads as None`, which lost its space after the comma. The check is unchanged; this is a stray whitespace edit.
   Suggested: Put back the original `check("no frontmatter reads as None", tf.read_frontmatter(...` spacing so the diff touches only new tests.
   Also reported: The verifier flagged edits to existing tests. Every change in test\_land.py is an added line. In test\_todofile.py, the only changed pre-existing line is the 'no frontmatter reads as None' check, which lost the space after its comma. The assertion is unchanged, so this is justified and harmless, but the edit was unnecessary and adds an E231 style nit.
   Also reported: Flagged edit to an existing test: the only change to a pre-existing line is a dropped space after the comma in check("no frontmatter reads as None",tf...). The assertion is unchanged and not weakened, but the whitespace edit is unrelated to the todo. The test\_land.py edits are purely additive and justified.
   Also reported: Formatting nit: missing space after comma in check("no frontmatter reads as None",tf...), introduced by the edit.
   Also reported: This is the only edit to an existing test in either file: it drops the space after the comma in the existing 'no frontmatter reads as None' check. The assertion does not change, so the edit is harmless, but nothing calls for it. The test\_land.py changes are additions only, and they match the 475 behaviour.
   Also reported: Verifier-flagged test edit: the only change to an existing test is the removed space after the comma in check("no frontmatter reads as None",tf.read\_frontmatter(...)). The assertion is unchanged, so this is a whitespace edit with no reason. All other test\_todofile.py changes, and every test\_land.py change (81 lines added, none removed), are new todo-475 tests and are justified.
   Also reported: Unrelated whitespace edit to an existing test: the space after the comma in check("no frontmatter reads as None", ...) was removed. It changes no behaviour and was not needed, but it adds an E231 style regression. The test\_land.py edits are additions only and are justified.
   Also reported: Formatting nit: `check("no frontmatter reads as None",tf.read_frontmatter(...` is missing a space after the comma (the original line had one).

11. **`scripts/todos/todofile.py:53`** (low, round 1, round 2). key\_line returns the FIRST matching line, but PyYAML safe\_load keeps the LAST duplicate key. On a file the old bug already damaged (`source_review : a` plus an appended `source_review: b`), set\_fields rewrites the dead line and the live pointer stays stale with no error. The old startswith match hit the live line. No such file exists in todos/ today.
   Suggested: In field\_problem, collect every line that key\_line's pattern matches. When there is more than one, return "'\<key>' is set on more than one line" so set\_fields and \_unsettable refuse instead of rewriting the shadowed line.
   Also reported: key\_line returns the first matching line. A file the old bug already corrupted (`source_review : a` plus an appended `source_review: b`) has its first line rewritten while YAML reads the last, so the pointer stays wrong without any warning. No such file exists in todos/ today.

12. **`scripts/todos/todofile.py:68`** (low, round 2). key\_line returns the FIRST matching line, but YAML keeps the LAST of duplicate keys. With 'source\_review: a' plus a quoted '"source\_review": b', field\_problem returns None (verified). The rewrite lands on the shadowed line, so the pointer still dangles while it is reported as rewritten.
   Suggested: When the key is found, also check that the parsed value is the one on that line, or count every occurrence of the key and refuse 'set on more than one line' if there are several.

13. **`scripts/todos/todofile.py:74`** (low, round 2). field\_problem catches only yaml.YAMLError, so 'malformed YAML keeps the old append behaviour' is not always true. With an invalid date elsewhere (e.g. created: 2026-02-30), PyYAML raises ValueError (verified), and set\_fields now raises on an absent key where it used to append.
   Suggested: Catch (yaml.YAMLError, ValueError) around parse\_frontmatter in field\_problem, or correct the comment so the fallback isn't overstated.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-09-30: Filed from todo-sweep run 2026-10-01-0121, PR #908 review rounds 1-2.
