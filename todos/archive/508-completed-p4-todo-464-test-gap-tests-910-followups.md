---
status: completed
priority: p4
issue_id: "508"
tags: [testing, backend, web]
dependencies: []
triage: ready
triaged: 2026-10-01
owner_decision: "Finding 1: no mutation run of reactions.py; record in the Work Log that the FOR UPDATE window check is unproven against mutation (2026-10-01)"
---

# Todo 464 test-gap tests: non-blocking findings from PR #910 (todo 487)

## Problem

PR #910 (todo 487) merged after two review rounds in todo-sweep run 2026-10-01-0121. The findings below were rated non-blocking, so they were not repaired. Findings at the same file:line are merged; each one says which round reported it. Line numbers are as of the PR head. Re-check each finding against main before acting on it.

## Findings

1. **`todos/archive/487-completed-p4-test-gap-tests-followups.md:52`** (medium, round 1). AC1 is ticked [x] but its own Work Log says no mutation run was done (classifier refused editing reactions.py). The only evidence is a diagnostic print plus a green run, which proves the new lock test passes, not that it fails without select\_for\_update.
   Suggested: Run the mutation (remove select\_for\_update from Reaction.recount, expect red, restore, assert git status clean) and record it, or leave AC1 unchecked / state the gap in the AC line.

2. **`backend/apps/plant_identification/tests/test_plantnet_circuit_breaker.py:43`** (low, round 2). The new fail-max test lives in its own class and asserts the literal 5 twice (the constant and the breaker's fail\_max). That does pin the threshold. The first assertion duplicates the second's intent.
   Suggested: Optional: keep only the plantnet\_service.\_plantnet\_circuit.fail\_max assertion plus the constant check, or fold both into the existing class.

3. **`backend/packages/wagtail_forum/wagtail_forum/tests/api/test_replies_reactions.py:338`** (low, round 1, round 2). New lock test imports connection and CaptureQueriesContext inside the function body, and matches SQL by string prefix, so it is brittle to ORM SQL formatting; the 'FOR UPDATE' window check is unmutated, so its discrimination is unproven.
   Suggested: Move the imports to module level; mutation-check by removing select\_for\_update before relying on the test.
   Also reported: The new lock test matches SQL text ('FOR UPDATE', 'UPDATE "table"' with reaction\_counts). It passes on Postgres but is brittle to ORM SQL formatting, and a backend without FOR UPDATE support would fail it. Behaviour matches reactions.py:50 select\_for\_update.
   Also reported: The new FOR UPDATE test was never mutation-verified (the Work Log admits it). It checks for a post-table FOR UPDATE between the INSERT and the reaction\_counts UPDATE, which any unrelated lock in that window would satisfy.
   Also reported: New lock test imports connection/CaptureQueriesContext inside the function body, and matches raw SQL text (startswith INSERT/UPDATE/SELECT ... FOR UPDATE). Brittle to quoting or ORM SQL-shape changes, though the failure message is clear.

4. **`backend/packages/wagtail_forum/wagtail_forum/tests/api/test_replies_reactions.py:353`** (low, round 2). Function-local imports of connection and CaptureQueriesContext inside the new test. Module-level imports are the convention, and this repo's change moved inline imports out of test\_ratelimits.py.
   Suggested: Hoist `from django.db import connection` and `from django.test.utils import CaptureQueriesContext` to module level.

5. **`backend/packages/wagtail_forum/wagtail_forum/tests/api/test_replies_reactions.py:376`** (low, round 1). The lock test only accepts a post FOR UPDATE strictly between the Reaction INSERT and the reaction\_counts UPDATE. A stronger fix, such as locking the post at the top of the view in an outer atomic so the existence check is serialized too, would wrongly fail it.
   Suggested: Accept any SELECT ... FOR UPDATE on the post table that comes before written[-1], not only one after inserted[-1]. Or document that the window deliberately pins recount's own lock.

6. **`backend/packages/wagtail_forum/wagtail_forum/tests/api/test_replies_reactions.py:379`** (low, round 2). The lock test accepts any post-table FOR UPDATE between the Reaction INSERT and the reaction\_counts UPDATE. If recount took the lock after its aggregate count SELECT, the count could still be stale under READ COMMITTED, yet the test would pass. The code is correct today.
   Suggested: Also locate the aggregate SELECT on the Reaction table (COUNT) and assert that the FOR UPDATE index comes before it, i.e. inserted[-1] \< lock \< count\_select \< written[-1].

7. **`todos/archive/487-completed-p4-test-gap-tests-followups.md:62`** (low, round 1). Work Log verification entries cite 'run 2026-10-01-0121' while dated 2026-09-30, and AC2/AC4/AC5/AC6 'evidence' are only greps for presence of text, not behavior.
   Suggested: Fix the run id/date; the pytest runs already cover behavior, so this is only a record-accuracy nit.

8. **`todos/archive/487-completed-p4-test-gap-tests-followups.md:71`** (low, round 2). Work Log dates the sweep entries 2026-09-30 but names run 2026-10-01-0121. The AC 2 evidence tail shows only neighbouring lines, not the assert text it claims to prove.
   Suggested: Align the dates, and quote the matching `the race hook never fired` line in the AC 2 evidence.

9. **`web/src/components/forum/forumMentionNode.test.ts:2`** (low, round 2). Finding 5 (Editor imported from the undeclared @tiptap/core) was fixed only in TipTapEditor.test.tsx. forumMentionNode.test.ts still imports Editor from '@tiptap/core', which web/package.json does not declare.
   Suggested: Import Editor from '@tiptap/react' here too (v3.31 does `export * from "@tiptap/core"`, so it is the same class), or declare @tiptap/core in package.json.

## Acceptance Criteria

- [x] Each finding above is fixed with a test, or the Work Log records why it was left as is.

## Work Log

- 2026-09-30: Filed from todo-sweep run 2026-10-01-0121, PR #910 review rounds 1-2.

### 2026-10-01 - Implemented by the todo sweep (run 2026-10-02-0118)

- Finding 1 left as is (owner decision 2026-10-01): no mutation run of `reactions.py` was done, so the FOR UPDATE window check in `test_reaction_toggle_recounts_under_a_post_row_lock` is unproven against mutation. That also covers finding 3's "mutation-check before relying on it". Todo 487's AC1 box is left untouched.
- Findings 3 and 4 fixed: `connection` and `CaptureQueriesContext` are module-level imports in `test_replies_reactions.py`. The SQL-text matching stays (left as is): the suite runs on Postgres only, and the failure message names the missing lock. Findings 5 and 6 fixed: the lock test now also finds recount's aggregate `SELECT ... COUNT(...) FROM "wagtail_forum_reaction"` and requires the post `FOR UPDATE` strictly between the Reaction INSERT and that COUNT, which comes before the `reaction_counts` UPDATE. A captured-SQL dump of one toggle shows INSERT at query 5, the locked post SELECT at 8, COUNT at 9 and the UPDATE at 10. The lower bound after the INSERT is kept on purpose and commented: the SQL log cannot show transaction scope, so the window pins recount's own lock.
- Finding 2 left as is: the two assertions pin different facts (the constant's value, and that the live breaker reads it), so dropping either loses a pin. The suggestion was marked optional.
- Findings 7 and 8 left as is: run ids are UTC (`RUN_ID = date -u +%Y-%m-%d-%H%M` in the completing-todos skill), so run 2026-10-01-0121 started on the evening of 2026-09-30 local time, and the dates in 487's Work Log are consistent with it. This entry has the same shape. The full AC 2 evidence file contains the `the race hook never fired` line; only the quoted tail omits it, and Land's archived Verified block is not rewritten.
- Finding 9 fixed: `forumMentionNode.test.ts` imports `Editor` from `@tiptap/react` (declared in `web/package.json`), so no test imports the undeclared `@tiptap/core` now.

### 2026-10-01 - Verified by the todo sweep (run 2026-10-02-0118)

- AC 1: `cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_6ca31bdb-4d9-1/backend && python3 ../scripts/todos/slot_env.py 1 -- /Users/williamtower/projects/plant_id_community/backend/venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_replies_reactions.py apps/plant_identification/tests/test_plantnet_circuit_breaker.py --create-db -v -p no:cacheprovider && cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_6ca31bdb-4d9-1/web && npx vitest run src/components/forum/forumMentionNode.test.ts && grep -n "^- Finding" /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_6ca31bdb-4d9-1/todos/508-pending-p4-todo-464-test-gap-tests-910-followups.md` — evidence `.sweep-evidence/g7/508-ac0.txt`, last lines:

  ```text
  60:- Finding 1 left as is (owner decision 2026-10-01): no mutation run of `reactions.py` was done, so the FOR UPDATE window check in `test_reaction_toggle_recounts_under_a_post_row_lock` is unproven against mutation. That also covers finding 3's "mutation-check before relying on it". Todo 487's AC1 box is left untouched.
  61:- Findings 3 and 4 fixed: `connection` and `CaptureQueriesContext` are module-level imports in `test_replies_reactions.py`. The SQL-text matching stays (left as is): the suite runs on Postgres only, and the failure message names the missing lock. Findings 5 and 6 fixed: the lock test now also finds recount's aggregate `SELECT ... COUNT(...) FROM "wagtail_forum_reaction"` and requires the post `FOR UPDATE` strictly between the Reaction INSERT and that COUNT, which comes before the `reaction_counts` UPDATE. A captured-SQL dump of one toggle shows INSERT at query 5, the locked post SELECT at 8, COUNT at 9 and the UPDATE at 10. The lower bound after the INSERT is kept on purpose and commented: the SQL log cannot show transaction scope, so the window pins recount's own lock.
  62:- Finding 2 left as is: the two assertions pin different facts (the constant's value, and that the live breaker reads it), so dropping either loses a pin. The suggestion was marked optional.
  63:- Findings 7 and 8 left as is: run ids are UTC (`RUN_ID = date -u +%Y-%m-%d-%H%M` in the completing-todos skill), so run 2026-10-01-0121 started on the evening of 2026-09-30 local time, and the dates in 487's Work Log are consistent with it. This entry has the same shape. The full AC 2 evidence file contains the `the race hook never fired` line; only the quoted tail omits it, and Land's archived Verified block is not rewritten.
  64:- Finding 9 fixed: `forumMentionNode.test.ts` imports `Editor` from `@tiptap/react` (declared in `web/package.json`), so no test imports the undeclared `@tiptap/core` now.
  ```

### 2026-10-01 - Completed by the todo sweep (run 2026-10-02-0118)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
