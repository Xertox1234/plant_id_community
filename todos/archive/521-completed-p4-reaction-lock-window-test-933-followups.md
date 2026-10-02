---
status: completed
priority: p4
issue_id: "521"
tags: [forum, backend, testing]
dependencies: []
triage: ready
triaged: 2026-10-02
owner_decision: "Finding 1: no mutation run - re-record 508's declining decision in 521's Work Log; findings 3/4: leave the archived 508 Verified block as is (508 precedent, matches todo 524's no-backfill decision) (2026-10-02)"
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

- [x] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-10-01: Filed from todo-sweep run 2026-10-02-0118, PR #933 review rounds 1-2.

### 2026-10-02 - Implemented by the todo sweep (run 2026-10-02-0335)

- Finding 1 left as is (owner decision 2026-10-02), re-recording todo 508's declining decision of 2026-10-01: no mutation run of `Reaction.recount` was done, so nobody has shown that dropping its `select_for_update`, or moving it after the COUNT, turns `test_reaction_toggle_recounts_under_a_post_row_lock` red. The lock-window check is still unproven against mutation. Its Postgres SQL-text match stays for 508's reason (the suite runs on Postgres only, and the failure message names the missing lock). The window's start after the INSERT is deliberate and commented in the test: the SQL log cannot show transaction scope, so the window pins recount's own lock, and a view that locks the post in an outer atomic must widen it on purpose.
- Finding 2 fixed: the lock window's upper bound is now `counted[0]`, the first reaction COUNT, not `counted[-1]` (`inserted[-1] < i < counted[0]`). A FOR UPDATE placed between two COUNTs now falls outside the window, so the test fails when the first COUNT ran unlocked (reasoned from the predicate; no mutation run, per finding 1). `Reaction.recount` issues one aggregate query today, and all 16 tests in the file pass before and after the change. The comment and the failure message name the first COUNT.
- Findings 3 and 4 left as is (owner decision 2026-10-02): the archived 508 Verified block is not rewritten, as 508 left 487's. Todo 524 fixed the cause of both at the source: `land.py` now rewrites worktree and main-checkout prefixes to repo-relative in a quoted command and its evidence tail, and rewrites the todo's own pre-archive path to its archived path. 524's owner decision was not to backfill already-archived lines, and 508's block is one of them. Finding 4's grep of `todos/508-pending-...` was valid when the verifier ran it, before the archive rename; to re-run it, grep `todos/archive/508-completed-p4-todo-464-test-gap-tests-910-followups.md`.
- Finding 3's date and run-id mismatch is a time-zone offset, not an error: run ids are UTC (`RUN_ID = date -u +%Y-%m-%d-%H%M` in `.claude/skills/completing-todos/SKILL.md`) and Work Log dates are local (`TODAY = date +%Y-%m-%d`). Run 2026-10-02-0118 started at 01:18 UTC on 2026-10-02, which was still the evening of 2026-10-01 local time, so 508's 2026-10-01 headings match it.

### 2026-10-02 - Verified by the todo sweep (run 2026-10-02-0335)

- AC 1: `cd backend && python3 scripts/todos/slot_env.py 4 -- backend/venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_replies_reactions.py --create-db -v -p no:cacheprovider && grep -nF "inserted[-1] < i < counted[0]" backend/packages/wagtail_forum/wagtail_forum/tests/api/test_replies_reactions.py && grep -n "^- Finding" todos/archive/521-completed-p4-reaction-lock-window-test-933-followups.md` — evidence `.sweep-evidence/g10/521-ac0.txt` (not committed), last lines:

  ```text
  399:        if inserted[-1] < i < counted[0]
  45:- Finding 1 left as is (owner decision 2026-10-02), re-recording todo 508's declining decision of 2026-10-01: no mutation run of `Reaction.recount` was done, so nobody has shown that dropping its `select_for_update`, or moving it after the COUNT, turns `test_reaction_toggle_recounts_under_a_post_row_lock` red. The lock-window check is still unproven against mutation. Its Postgres SQL-text match stays for 508's reason (the suite runs on Postgres only, and the failure message names the missing lock). The window's start after the INSERT is deliberate and commented in the test: the SQL log cannot show transaction scope, so the window pins recount's own lock, and a view that locks the post in an outer atomic must widen it on purpose.
  46:- Finding 2 fixed: the lock window's upper bound is now `counted[0]`, the first reaction COUNT, not `counted[-1]` (`inserted[-1] < i < counted[0]`). A FOR UPDATE placed between two COUNTs now falls outside the window, so the test fails when the first COUNT ran unlocked (reasoned from the predicate; no mutation run, per finding 1). `Reaction.recount` issues one aggregate query today, and all 16 tests in the file pass before and after the change. The comment and the failure message name the first COUNT.
  47:- Findings 3 and 4 left as is (owner decision 2026-10-02): the archived 508 Verified block is not rewritten, as 508 left 487's. Todo 524 fixed the cause of both at the source: `land.py` now rewrites worktree and main-checkout prefixes to repo-relative in a quoted command and its evidence tail, and rewrites the todo's own pre-archive path to its archived path. 524's owner decision was not to backfill already-archived lines, and 508's block is one of them. Finding 4's grep of `todos/508-pending-...` was valid when the verifier ran it, before the archive rename; to re-run it, grep `todos/archive/508-completed-p4-todo-464-test-gap-tests-910-followups.md`.
  48:- Finding 3's date and run-id mismatch is a time-zone offset, not an error: run ids are UTC (`RUN_ID = date -u +%Y-%m-%d-%H%M` in `.claude/skills/completing-todos/SKILL.md`) and Work Log dates are local (`TODAY = date +%Y-%m-%d`). Run 2026-10-02-0118 started at 01:18 UTC on 2026-10-02, which was still the evening of 2026-10-01 local time, so 508's 2026-10-01 headings match it.
  ```

### 2026-10-02 - Completed by the todo sweep (run 2026-10-02-0335)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
