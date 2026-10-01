---
status: completed
priority: p4
issue_id: "487"
tags: [testing, backend, web, forum]
dependencies: []
source_review: "PR #879"
triage: ready
triaged: 2026-09-30
---

# Todo 464's new tests: non-blocking findings from PR #879

## Problem

PR #879 added tests for four behaviours that had shipped untested. Both review rounds were
clean. These are the non-blocking findings.

## Findings

1. **`Reaction.recount`'s row lock is still untested.** The race test runs both requests on one
   connection in one transaction, so it proves only the unique-constraint double INSERT.
   Deleting `select_for_update` in `Reaction.recount` leaves the suite green. Todo 464's AC 2 asked
   for "a ReactionToggleView concurrency test", and its Work Log says the lock half was reasoned,
   not tested (`test_replies_reactions.py:281`).
2. **The race test fails obscurely if the view changes shape.** The interleave hooks
   `Reaction.objects.filter(...).first()`. If the view switches to `.exists()` or `.get()`, the test
   dies with a bare `KeyError: 'a'`. Assert the hook fired first (`test_replies_reactions.py:322`).
3. **The breaker tests track the constant instead of pinning it.** Both derive their failure count
   from `PLANTNET_CIRCUIT_FAIL_MAX`, so shrinking it to 1 still passes. Pin the documented 5
   (`test_plantnet_circuit_breaker.py:76`; the `docs/rules/testing.md` constant-tracking rule).
4. **A comment is wrong.** "A distinct colour per call keeps each cache key distinct" is false:
   after the JPEG q85 re-encode, `(0,0,0)` and `(1,0,0)` are byte-identical
   (`test_plantnet_circuit_breaker.py:73`). The test is still correct, because failures are never
   cached.
5. **`Editor` comes from an undeclared package.** `TipTapEditor.test.tsx:5` imports it from
   `@tiptap/core`, which `web/package.json` does not declare. `@tiptap/react` re-exports it.
6. **A 15-line upload closure is duplicated** across two tests in `test_ratelimits.py:361`.

## Acceptance Criteria

- [x] A test fails when `select_for_update` is removed from `Reaction.recount` (for example, a
      `CaptureQueriesContext` assertion for `FOR UPDATE`), or this todo records why not.
- [x] The race test asserts that its hook fired before reading the result.
- [x] `PLANTNET_CIRCUIT_FAIL_MAX == 5` is pinned with a literal.
- [x] The cache-key comment is corrected, or the colours are spread far enough apart to survive
      JPEG.
- [x] `TipTapEditor.test.tsx` imports `Editor` from `@tiptap/react`.
- [x] The upload helper is shared.

## Work Log

### 2026-09-28 - Filed from PR #879 rounds 1 and 2 (todo sweep run 2026-09-28-2018)

### 2026-09-30 - Implemented by the todo sweep (run 2026-10-01-0121)

- Added `test_reaction_toggle_recounts_under_a_post_row_lock`: it captures the SQL of one
  reaction toggle and requires a `SELECT ... FOR UPDATE` on the post table between the Reaction
  INSERT and the `reaction_counts` UPDATE. A diagnostic print of the captured SQL showed exactly
  one `FOR UPDATE` in the whole request, inside `recount`'s savepoint, so removing
  `select_for_update` leaves none and the test fails. A live mutation run of `reactions.py` was
  not done: the session's permission classifier refused editing that source file.
- The race test now asserts its `QuerySet.first` hook fired before it reads `raced["a"]`, with a
  message naming the likely cause, so a view reshape no longer ends in a bare `KeyError`.
- Pinned `PLANTNET_CIRCUIT_FAIL_MAX == 5` (and the live breaker's `fail_max == 5`) with literals,
  and corrected the cache-key comment. Before writing it, I checked that `(0,0,0)` and `(1,0,0)`
  hash identically after the service's q85 re-encode.
- `TipTapEditor.test.tsx` imports `Editor` from `@tiptap/react`, which re-exports
  `@tiptap/core`. The duplicated image-upload closure in `test_ratelimits.py` is now one
  module-level `_upload_image(client)` helper.

### 2026-09-30 - Verified by the todo sweep (run 2026-10-01-0121)

- AC 1: `cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_b783a27f-977-1/backend && python3 ../scripts/todos/slot_env.py 1 -- /Users/williamtower/projects/plant_id_community/backend/venv/bin/python -m pytest packages/wagtail_forum/wagtail_forum/tests/api/test_replies_reactions.py::test_reaction_toggle_recounts_under_a_post_row_lock packages/wagtail_forum/wagtail_forum/tests/api/test_replies_reactions.py::test_simultaneous_reaction_toggles_leave_one_row_and_a_consistent_count --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g7/487-ac0.txt`, last lines:

  ```text
    /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_b783a27f-977-1/backend/packages/wagtail_forum/wagtail_forum/api/image_management.py:32: RemovedInWagtail90Warning: wagtail.images.permissions.permission_policy is deprecated. Use wagtail.permissions.policy_registry.get_by_type(get_image_model()) instead.
      from wagtail.images import permissions as image_permissions

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 2 passed, 3 warnings in 16.07s ========================
  ```

- AC 2: `grep -n -B3 -A6 "the race hook never fired" /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_b783a27f-977-1/backend/packages/wagtail_forum/wagtail_forum/tests/api/test_replies_reactions.py` — evidence `.sweep-evidence/g7/487-ac1.txt`, last lines:

  ```text
  327-    )
  328-    a = raced["a"]
  329-    assert a.status_code == b.status_code == 200
  330-    assert a.data["reacted"] is True
  331-    assert b.data["reacted"] is True  # the loser reports the state that won
  ```

- AC 3: `cd /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_b783a27f-977-1/backend && python3 ../scripts/todos/slot_env.py 1 -- /Users/williamtower/projects/plant_id_community/backend/venv/bin/python -m pytest apps/plant_identification/tests/test_plantnet_circuit_breaker.py --create-db -v -p no:cacheprovider` — evidence `.sweep-evidence/g7/487-ac2.txt`, last lines:

  ```text
    /Users/williamtower/projects/plant_id_community/backend/venv/lib/python3.13/site-packages/fuzzywuzzy/fuzz.py:11: UserWarning: Using slow pure-python SequenceMatcher. Install python-Levenshtein to remove this warning
      warnings.warn('Using slow pure-python SequenceMatcher. Install python-Levenshtein to remove this warning')

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ======================== 3 passed, 2 warnings in 0.26s =========================
  ```

- AC 4: `grep -n -B2 -A4 "byte-identical" /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_b783a27f-977-1/backend/apps/plant_identification/tests/test_plantnet_circuit_breaker.py` — evidence `.sweep-evidence/g7/487-ac3.txt`, last lines:

  ```text
  85:        # (0,0,0) and (1,0,0) come out byte-identical. They do not need to --
  86-        # failures are never cached, so every call still reaches the HTTP layer.
  87-        for i in range(PLANTNET_CIRCUIT_FAIL_MAX):
  88-            with self.assertRaises(ExternalAPIError):
  89-                service.identify_plant([_jpeg((i, 0, 0))])
  ```

- AC 5: `grep -n "@tiptap/" /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_b783a27f-977-1/web/src/components/forum/TipTapEditor.test.tsx` — evidence `.sweep-evidence/g7/487-ac4.txt`, last lines:

  ```text
  5:import { Editor } from '@tiptap/react';
  1092:    // `setTimeout` it schedules on unmount (@tiptap/react's
  ```

- AC 6: `grep -n "_upload_image\|def upload\|PILImage\|SimpleUploadedFile" /Users/williamtower/projects/plant_id_community/.claude/worktrees/wf_b783a27f-977-1/backend/apps/forum_host/tests/test_ratelimits.py` — evidence `.sweep-evidence/g7/487-ac5.txt`, last lines:

  ```text
  341:        blocked = _upload_image(client)
  363:        first = _upload_image(client)
  364:        blocked = _upload_image(client)
  366:        after_window = _upload_image(client)
  367:        blocked_again = _upload_image(client)
  ```

### 2026-09-30 - Completed by the todo sweep (run 2026-10-01-0121)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
