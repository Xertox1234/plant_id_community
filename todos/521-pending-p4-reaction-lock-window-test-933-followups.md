---
status: pending
priority: p4
issue_id: "521"
tags: [forum, backend, testing]
dependencies: []
---

# Reaction lock window test: non-blocking findings from PR #933 (todo 508)

## Problem

PR #933 (todo 508) merged after two review rounds in todo-sweep run 2026-10-02-0118. The findings below were rated non-blocking, so they were not repaired. Findings at the same file:line are merged; each one says which round reported it. Line numbers are as of the PR head. Re-check each finding against main before acting on it.

## Findings

1. **`backend/packages/wagtail_forum/wagtail_forum/tests/api/test_replies_reactions.py:376`** (low, round 1, round 2). The tightened lock-before-COUNT window has never been mutation-checked (owner decision in todo 508). Nobody has shown that removing select\_for\_update, or moving it after the COUNT, turns this test red. The check is also tied to Postgres SQL text.
   Suggested: Before relying on it, do one local mutation run: drop select\_for\_update in Reaction.recount, expect red, restore, confirm git status is clean. Record the result in the todo Work Log.
   Also reported: The reworked lock-before-COUNT window was not mutation-checked, as the todo's Work Log admits. Nothing shows the test goes red when the FOR UPDATE moves after the COUNT. The window also starts after the INSERT, so an outer-atomic lock would fail it.

2. **`backend/packages/wagtail_forum/wagtail_forum/tests/api/test_replies_reactions.py:397`** (low, round 2). The lock window's upper bound is counted[-1], the last reaction COUNT. If recount ever runs two COUNTs, a FOR UPDATE placed between them would pass even though the first COUNT ran unlocked. The current recount runs one COUNT, so the test is correct today.
   Suggested: Bound the window with counted[0] (`inserted[-1] < i < counted[0]`) so the lock has to come before the first aggregate read of the reaction rows.

3. **`todos/archive/508-completed-p4-todo-464-test-gap-tests-910-followups.md:60`** (low, round 1, round 2). Work Log quotes absolute worktree paths (.claude/worktrees/wf\_...) in the Verified block; these are ephemeral and meaningless after the worktree is removed.
   Suggested: Acceptable as sweep evidence; optionally use repo-relative paths in the recorded command.
   Also reported: Work Log headings are dated 2026-10-01 but cite run id 2026-10-02-0118, and the Verified command embeds an absolute worktree path. The UTC reasoning in finding 7/8 explains the date skew only loosely.
   Also reported: Work Log headings are dated 2026-10-01 but name run 2026-10-02-0118, so the heading date and the run id disagree.

4. **`todos/archive/508-completed-p4-todo-464-test-gap-tests-910-followups.md:76`** (low, round 2). The recorded AC1 verify command greps the todos/508-pending-... path, which no longer exists after the archive rename. Anyone re-running the evidence command gets a grep error on that path.
   Suggested: Note that the path was valid pre-archive, or point the grep at the archived path.

## Acceptance Criteria

- [ ] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-10-01: Filed from todo-sweep run 2026-10-02-0118, PR #933 review rounds 1-2.
