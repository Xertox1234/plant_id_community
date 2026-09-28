---
status: completed
priority: p3
issue_id: "464"
tags: [testing, tech-debt]
dependencies: []
source_review: "todos/archive/394-completed-p3-triage-the-grandfathered-archived-todos.md"
triage: ready
triaged: 2026-09-28
---

# Four behaviours whose code landed but was never tested (or lost its test)

## Problem

The todo 394 triage found three archived todos whose code is live but
whose test AC never landed. Each file is now `superseded` with a pointer
here.

- **PlantNet circuit breaker** (from 001): `plantnet_service.py` wraps
  calls in `create_monitored_circuit("plantnet_api")`, but
  `test_circuit_breaker_locks.py` exercises only `_plant_id_circuit`.
  Nothing shows the PlantNet breaker opening after 5 failures and then
  failing fast without an HTTP call.
- **Reaction toggle concurrency** (from 004-reaction): `wagtail_forum`'s
  `ReactionToggleView` relies on a `UniqueConstraint` plus an atomic create
  that catches `IntegrityError`, and `Reaction.recount` locks the Post row.
  The only tests are sequential.
- **TipTap destroy on unmount** (from 015):
  `web/src/components/forum/TipTapEditor.tsx:633-640` calls `destroy()` in
  cleanup, but no test spies on it.
- **Upload throttle window reset** (from 009-upload, PR #859 review): the
  old forum had `test_rate_limit_resets_after_timeout` (3ad067c0). The
  rebuilt `forum_host` throttle (`api.py:81`) is tested only for the 429.

## Acceptance Criteria

- [x] A PlantNet breaker test: after N failures the breaker is open, and
      the next call raises without touching the HTTP layer.
- [x] A `ReactionToggleView` concurrency test (threads or a
      `TransactionTestCase`): two simultaneous toggles leave a consistent
      count and at most one row.
- [x] A TipTap test asserting `destroy()` runs on unmount.
- [x] A `forum_host` image-upload throttle test: after the window passes,
      uploads are allowed again.
- [x] Each test fails with its guard removed (mutation-checked).

## Work Log

### 2026-09-28 - Implemented by the todo sweep (run 2026-09-28-2018)

- PlantNet breaker: new `backend/apps/plant_identification/tests/test_plantnet_circuit_breaker.py`
  drives `PLANTNET_CIRCUIT_FAIL_MAX` real failures through `identify_plant`, asserts the
  module-level `_plantnet_circuit` is `open`, and that the next call raises the 503
  "temporarily unavailable" error with `requests.Session.post` still at FAIL_MAX calls.
  A second test pins that FAIL_MAX-1 failures leave it closed (the fast-fail is the breaker's).
- Reaction race: `test_simultaneous_reaction_toggles_leave_one_row_and_a_consistent_count`
  in `wagtail_forum/tests/api/test_replies_reactions.py` (not `tests/test_reactions.py`:
  that file is model-level and has no API urlconf). Not threads/TransactionTestCase:
  `docs/rules/testing.md` bans `django_db(transaction=True)` (its flush deletes the seeded
  Wagtail root). The interleaving is forced instead: request B's real SELECT finds nothing,
  request A then runs to completion, B's INSERT hits the unique constraint. Both 200, one
  row, `reaction_counts == {"like": 1}`. `Reaction.recount`'s `select_for_update` only
  matters across connections and is NOT exercised by this test (reasoning-verified only).
- TipTap: `destroy()` is asserted synchronously right after `unmount()`. `@tiptap/react`
  3.x `useEditor` also destroys, but from a `setTimeout` (`scheduleDestroy`), so a plain
  spy would pass with the component's cleanup removed; the synchronous check does not.
- Upload throttle: `test_image_upload_throttle_resets_after_the_window` in
  `forum_host/tests/test_ratelimits.py`: 201, 429, then +1 h 1 s later 201 and 429 again.
- Mutation-checked by a script in the sweep's (uncommitted) evidence dir: six mutants (breaker
  bypassed; IntegrityError not caught; INSERT outside its savepoint; destroy cleanup
  removed; upload throttle removed; ratelimit window frozen), all killed, files restored.

### 2026-09-28 - Verified by the todo sweep (run 2026-09-28-2018)

- AC 1: `python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-2/scripts/todos/slot_env.py 5 -- /Users/williamtower/projects/plant_id_community/backend/venv/bin/python -m pytest /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-2/backend/apps/plant_identification/tests/test_plantnet_circuit_breaker.py --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g7/464-ac0.txt`, last lines:

  ```text
    /Users/williamtower/projects/plant_id_community/backend/venv/lib/python3.13/site-packages/fuzzywuzzy/fuzz.py:11: UserWarning: Using slow pure-python SequenceMatcher. Install python-Levenshtein to remove this warning
      warnings.warn('Using slow pure-python SequenceMatcher. Install python-Levenshtein to remove this warning')

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 2 passed, 2 warnings in 0.29s =========================
  ```

- AC 2: `python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-2/scripts/todos/slot_env.py 5 -- /Users/williamtower/projects/plant_id_community/backend/venv/bin/python -m pytest /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-2/backend/packages/wagtail_forum/wagtail_forum/tests/api/test_replies_reactions.py::test_simultaneous_reaction_toggles_leave_one_row_and_a_consistent_count --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g7/464-ac1.txt`, last lines:

  ```text
    /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-2/backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 1 passed, 3 warnings in 16.65s ========================
  ```

- AC 3: `/Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-2/web/node_modules/.bin/vitest run --root /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-2/web src/components/forum/TipTapEditor.test.tsx -t "unmount cleanup"` — evidence `.sweep-evidence/g7/464-ac2.txt`, last lines:

  ```text

   Test Files  1 passed (1)
        Tests  1 passed | 58 skipped (59)
     Start at  15:35:37
     Duration  1.12s (transform 130ms, setup 110ms, import 407ms, tests 51ms, environment 478ms)
  ```

- AC 4: `python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-2/scripts/todos/slot_env.py 5 -- /Users/williamtower/projects/plant_id_community/backend/venv/bin/python -m pytest /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-2/backend/apps/forum_host/tests/test_ratelimits.py::test_image_upload_throttle_resets_after_the_window --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g7/464-ac3.txt`, last lines:

  ```text
    /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-2/backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 1 passed, 3 warnings in 16.91s ========================
  ```

- AC 5: `python3 /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_82aa03f6-6f2-2/.sweep-evidence/g7/464-mutation-check.py` — evidence `.sweep-evidence/g7/464-ac4.txt`, last lines:

  ```text
    ======================== 1 failed, 3 warnings in 17.57s ========================
  restored byte-identical: True
  RESULT: OK -- mutant killed

  ALL MUTANTS KILLED
  ```

### 2026-09-28 - Completed by the todo sweep (run 2026-09-28-2018)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
