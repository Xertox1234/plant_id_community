---
status: pending
priority: p4
issue_id: "514"
tags: [tooling, todo-sweep]
dependencies: []
---

# Sweep fixer tolerance: non-blocking findings from PR #924 (todo 513)

## Problem

PR #924 (todo 513) merged after two review rounds in todo-sweep run 2026-10-01-2355. The findings below were rated non-blocking, so they were not repaired. Findings at the same file:line are merged; each one says which round reported it. Line numbers are as of the PR head. Re-check each finding against main before acting on it.

## Findings

1. **`.claude/skills/completing-todos/SKILL.md:180`** (low, round 1, round 2). The recovery stages the paths printed by `git diff --name-only`, which has no -z. Under core.quotePath, git prints a non-ASCII or special-character path quoted with octal escapes, so the `git add <paths>` copied from that output fails with 'pathspec did not match'.
   Suggested: Use `/usr/bin/git -C $WT diff --name-only -z | xargs -0 /usr/bin/git -C $WT add --`, or `-c core.quotePath=false`.
   Also reported: The recovery stages 'exactly the paths `git diff --name-only` prints'. Without -z, git C-quotes paths that contain unusual characters (core.quotePath), so `git add <paths>` can miss the right file or name the wrong one. ensure-worktree still fails closed afterwards.
   Also reported: The new step-6 recovery says a refusal 'means the diff is more than a fixer made: stop the group'. But the configured fixers mixed-line-ending --fix=lf (CRLF->LF, refused by owner choice) and markdownlint --fix/black/isort also rewrite files, and those changes are refused. Operators are told the wrong reason.

2. **`.claude/skills/completing-todos/SKILL.md:182`** (low, round 1, round 2). Step 6 reads a refusal as 'more than a fixer made', but the config also runs fixers outside the port: black, isort, prettier, dart-format, markdownlint --fix and mixed-line-ending. A Land commit on a verified .md or backend .py they rewrite stops the group with a misleading reason.
   Suggested: Say that only trailing-whitespace and end-of-file-fixer rewrites are accepted. A refusal can also mean another configured fixer (black, markdownlint --fix, mixed-line-ending) rewrote the file. The action stays: stop the group.
   Also reported: 'A refusal there means the diff is more than a fixer made' is inaccurate. Other configured fixers also rewrite staged files on the Land commit and are refused: markdownlint --fix on .md (it runs after end-of-file-fixer), mixed-line-ending, black and isort on backend/*.py. A benign formatter abort then reads as a real change.

3. **`scripts/todos/state.py:1156`** (low, round 1, round 2). The text test is just 'no NUL byte'. Pre-commit runs these fixers only on files identify calls text, and identify also calls a file binary for control bytes (0x01-0x06, 0x0e-0x1a, 0x7f) in its first 1KB or for a binary extension. The fixers skip such a file, but the port still accepts a whitespace-stripped version of it.
   Suggested: Use identify's own rule: refuse when before.translate(None, TEXTCHARS) over the first 1024 bytes is non-empty, with TEXTCHARS = {7..13, 27} | 0x20-0xff minus 0x7f. Add a test with a \\x01 byte.
   Also reported: The binary gate only checks for a NUL byte. pre-commit runs both fixers only on files that identify tags `text`, and identify decides by extension first (.png, .pdf, .ico...) and otherwise by any control byte outside {7-13,27} or 0x7f. A whitespace edit shaped like fixer output on such a file is accepted, although no fixer could have made it.
   Also reported: \_fixer\_only\_change treats any file without a NUL byte as text. The real hooks run only on files pre-commit/identify tags `text`, which uses the extension first, then the first 1024 bytes (0x01-0x06, 0x0e-0x1f except ESC, and 0x7f count as binary). A whitespace-stripped non-text file still passes as the fixers' output.
   Also reported: The binary gate is only 'contains NUL'. pre-commit's identify tags as binary any file with other control bytes (e.g. \\x01, \\x7f) in its first 1 KB, or with a binary extension, and the fixers skip those files. The port still accepts a fixer-shaped whitespace edit on such a file, which no hook made.

4. **`scripts/todos/state.py:1158`** (low, round 1). The fixer gate accepts F(verified bytes) for files the real hooks never rewrite: identify's types:[text] skips files with control bytes such as 0x01-0x06 or 0x7f in their first 1 KB, and the gate only checks for NUL. Files left out of the commit get the same pass. The accepted bytes are still fixed by the reviewed bytes.
   Suggested: Also fail closed when the verified blob's first 1024 bytes contain a byte outside identify's \_TEXTCHARS ({7..13,27} | 0x20-0xff minus 0x7f), so the gate matches the hook's text filter.
   Also reported: Whitespace stripping that changes meaning passes with no re-verification. A shell line ending in a backslash and a space becomes a line continuation once the space is stripped, and string literals lose whitespace. The owner accepted this risk (finding 8), but only the .py literal case has a test.
   Also reported: The port checks only for NUL bytes, but the hooks run only on files identify tags as text. That skips binary extensions and content with control bytes such as \\x01 or \\x7f. A whitespace-only edit to such a file is accepted even though no fixer could have made it.

5. **`scripts/todos/state.py:1168`** (low, round 1, round 2). \_fixer\_output hand-reimplements the pre-commit fixers (v4.5.0). A hook version bump can silently diverge, and the tests only pin the reimplementation against itself, not against the real hooks.
   Suggested: Add one test that runs the real trailing-whitespace/end-of-file-fixer on a fixture and compares to \_fixer\_output, or note the pinned version next to the config.
   Also reported: \_fixer\_output models only trailing-whitespace + end-of-file-fixer, but .pre-commit-config.yaml also runs markdownlint --fix on .md before them. MD009's fix deletes all 3+ trailing spaces, while the port keeps two, so that Land rewrite is refused. Todo 512 accepted it. (MD009 behaviour is a hypothesis from its source, not run.)
   Also reported: \_fixer\_output ports hook behaviour by hand. The todo records an 800,000-input differential run, but that run is scratch-only, so a pre-commit-hooks version bump can drift from it with no failing test.

6. **`scripts/todos/test_state_flow.py:810`** (low, round 1). The edits to existing tests are justified: the old inputs kept a tab or dropped a .md hard break, which the real hooks never do, and the wave/empty-commit checks got stronger. Still untested: the md hard-break normalisation of 3+ trailing spaces or a tab down to exactly two spaces, the uppercase .MD extension, and a 100755 file.
   Suggested: Add accepted cases: doc.md 'text \\t  ' becomes 'text  ', a NOTES.MD hard break is kept, and a 100755 script loses its trailing space. Add a refusing case for 'text   ' left with three spaces.

7. **`scripts/todos/test_state_flow.py:815`** (low, round 1, round 2). The test accepts a CRLF-preserving result as 'the fixers' output', but the configured chain (mixed-line-ending --fix=lf) always turns CRLF into LF. That result can only come from a hand edit or SKIP=, so it contradicts the docstring's claim of 'exactly the configured fixers' output'.
   Suggested: Keep the behaviour if intended, but relabel the test and docstring: 'trailing-whitespace + end-of-file-fixer output only; mixed-line-ending is not modelled'. Or refuse when before contains b'\\r'.
   Also reported: This test pins acceptance of a CRLF-preserving rewrite. The real hook chain never produces it, because mixed-line-ending --fix=lf runs after the two fixers and converts the file to LF, which refuses. So it accepts bytes no hook wrote, against the commit's 'only the hooks' real output' intent. The bytes are whitespace-only, so it is harmless.

8. **`scripts/todos/test_state_flow.py:838`** (low, round 2). The 'empty commit keeps the index tree and HEAD's tree' and 'nothing staged after Land commit' checks only assert git's own behaviour; no repo code runs. The runbook's diff --cached/HEAD~1^{tree} guard is pinned by substring only, so they would pass whatever SKILL.md says.
   Suggested: Keep the \_land\_only\_diff-driving ensure\_worktree assertion (that one is real). Drop or label the tautological git checks so they are not counted as coverage of the runbook recovery.

9. **`scripts/todos/test_state_flow.py:1420`** (low, round 1). The timeout parity test only checks hook timeout >= GATE\_TIMEOUT (300 == 300). Hook setup plus the gate's own work can exceed 300 s, so equality leaves no margin, and the test would still pass at equality.
   Suggested: Require a margin (hook timeout > GATE\_TIMEOUT), or document that equality is intended and why the hook's own overhead fits.

10. **`.claude/hooks/kimi-review.sh`** (low, worker discovery in todo 513, not a reviewer finding). The hook's command regex never matches `/usr/bin/git -C <wt> commit` or `git -C … commit`, so it never fires on a sweep Land commit; only the pre-commit kimi gate runs there. Re-check on main, then either widen the regex (with a `test-kimi-review.sh` case) or record that the pre-commit gate is the intended one for `-C` commits.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-10-01: Filed from todo-sweep run 2026-10-01-2355, PR #924 review rounds 1-2.
