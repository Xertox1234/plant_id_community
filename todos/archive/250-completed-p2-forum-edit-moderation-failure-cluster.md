---
status: completed
priority: p2
issue_id: "250"
tags: [forum, wagtail, moderation, workflow, bug]
dependencies: []
source_review: "docs/reviews/2026-07-02-2252-forum-write-path-trial.md"
source_finding: "1"
---

# Fix the forum edit-moderation failure cluster (workflow wedge, NULL author, fake pending, missing signal)

## Context

Todo-244's review trial adversarially verified four related bugs in the forum
edit path (`submit_edit_for_moderation` + `PostWriteView.patch`), all
re-confirmed on main `d52cf14`. Findings #1–#4 + #13 in the source review.
The write path is merged but NOT yet deployed (Railway/CF), so these block the
forum-writes deploy rather than affecting prod today.

## Problem

`W = backend/packages/wagtail_forum/wagtail_forum`

1. **Workflow wedge** (`W/workflow.py:116`): Wagtail allows one active
   WorkflowState (IN_PROGRESS or NEEDS_CHANGES) per object. After one
   spam-rejected edit, every later `workflow.start()` raises
   `ValidationError` → swallowed → the post is permanently stuck "pending";
   no future edit is ever screened or published. Wagtail's own resubmit flow
   uses `current_workflow_state.resume()`/`cancel()`.
2. **NULL-author crash** (`W/workflow.py:108`): `ForumProfile.for_user(None)`
   raises for account-deleted authors (Post.author is SET_NULL) before
   `save_revision` — a moderator's redaction edit is silently lost, 200
   "pending" returned.
3. **Fake "pending"** (`W/api/views.py:407-413`): the blanket
   `except Exception → 'pending'` is only truthful on the create path (row
   persisted before submit). On edit, a failure before/inside `save_revision`
   persists nothing — the client is told an edit is queued that doesn't exist.
4. **Missing signal** (`W/workflow.py`): `submit_for_moderation` fires
   `moderation_decided` (line 82); `submit_edit_for_moderation` never does —
   hosts never hear about edit outcomes.
5. **(Plausible) PATCH/unpublish race** (#13): no atomicity between
   `_get_editable`'s `live` check and trusted-path `revision.publish()` — a
   PATCH racing a moderator DELETE can republish the just-deleted post.

## Recommended Action

- Handle an existing active workflow state before `workflow.start()` in
  `submit_edit_for_moderation` (resume or cancel+restart; spike against real
  Wagtail like the todo-231 spike did — see `docs/reviews/2026-06-23-…pr2a…`).
- Trust routing must tolerate `obj.author is None` (treat as untrusted/never
  autopublish, or route by the acting user for moderator edits — decide and
  document; today trust intentionally derives from `obj.author`).
- Narrow the PATCH except-wrapper: distinguish "revision saved, moderation
  submission failed" (pending is truthful) from "nothing persisted" (return
  an error, not 200).
- Fire `moderation_decided` on the edit path with the same contract as create.
- For the race: wrap the check+publish in `select_for_update` on the post row
  (or verify `live` inside the transaction) — confirm the mechanism before
  fixing; it is PLAUSIBLE, not confirmed.

## Technical Details

- Files: `W/workflow.py`, `W/api/views.py`,
  tests under `W/tests/workflow/` + `W/tests/api/test_post_edit_delete.py`.
- The flagged-edit → clean-edit sequence is currently untested (the trial
  noted the two tests use different posts) — the wedge fix needs exactly that
  regression test.
- Package tests must not import from `apps.*` (test_reusability).
- Backend convention: type-hint service methods (`submit_edit_for_moderation`
  is a bare `def` — fix while touching it; also claims finding #12's item).

## Acceptance Criteria

- [x] Regression test: flagged edit then clean edit on the SAME post — clean
      edit gets screened (published or genuinely pending), not wedged.
      (`test_flagged_then_clean_edit_not_wedged` PASSED)
- [x] Test: moderator PATCH on an author-deleted (author=None) post succeeds
      (redaction persists) or returns an explicit error — never a silent 200.
      (`test_moderator_edit_author_deleted_post_persists` +
      `test_author_deleted_moderator_edit_publishes` PASSED)
- [x] Test: an exception before `save_revision` does NOT return 200 "pending".
      (`test_edit_save_revision_failure_is_not_fake_pending` PASSED)
- [x] `moderation_decided` fires for edit outcomes (test with a signal receiver).
      (`test_edit_fires_moderation_decided` PASSED)
- [x] Race either fixed with a locking test or explicitly re-verified and
      documented as not reproducible. (Fixed: row lock + liveness re-read in
      `submit_edit_for_moderation` and `PostWriteView.delete`;
      `test_edit_does_not_resurrect_unpublished_post` PASSED)
- [x] Full forum suite green (`pytest` — see docs/rules/testing.md re: pytest
      runner and `--create-db` when changing app subsets). (143 package + 14
      host tests PASSED)

## Work Log

### 2026-07-02 - Created

- Filed from the todo-244 trial (findings #1–#4, #13), re-verified on main
  d52cf14 before filing.

### 2026-07-03 - Started by completing-todos skill (run 2026-07-03-2006)

- Picked up by automated workflow.

### 2026-07-03 - Implemented (TDD, advisor-reviewed)

All five findings fixed in `W/workflow.py` + `W/api/views.py`, plus a one-field
model change. TDD: wrote 7 failing tests first, watched them go RED, then fixed.

- **#1 wedge** — `submit_edit_for_moderation` now cancels an existing active
  `WorkflowState` (`obj.current_workflow_state.cancel()`) before `workflow.start()`.
  Spiked against real Wagtail 7.4 via the regression test (flagged→clean edit on
  the SAME post → publishes). Chose cancel+start over resume (handles both
  NEEDS_CHANGES and the theoretical IN_PROGRESS; after cancel the state is
  CANCELLED so `start()`'s `clean()` no longer trips).
- **#2 NULL author** — extracted `_edit_is_trusted(obj, acting_as_moderator)`:
  when `obj.author is None` (SET_NULL) it routes by the acting user (moderator →
  publish) instead of crashing on `ForumProfile.for_user(None)`; the view passes
  `acting_as_moderator=request.user.has_perm("wagtail_forum.change_post")` so
  `workflow.py` stays permission-agnostic. **Deeper half:** `save_revision()` →
  `full_clean()` rejected the blank author (`null=True` but `blank` unset), so a
  redaction still failed — added `blank=True` to `Post.author` (migration
  `0009_alter_post_author`, state-only, no SQL since `null=True` already exists).
- **#3 fake pending** — `save_revision` moved OUTSIDE the try/atomic (a
  pre-persist failure now propagates → 500, not a fake 200 pending); only the
  publish/workflow step is wrapped (there "pending" is truthful). View's blanket
  `except → pending` removed.
- **#4 signal** — `moderation_decided` fired after the critical section with the
  create-path contract, keyed off `has_unpublished_changes` (not `obj.live`).
- **#13 race** — advisor flagged that #3 and #5 fight over the transaction (a DB
  error inside `atomic` poisons the connection). Adopted shape (A): `save_revision`
  commits first, then a NARROW `atomic()` holds a `select_for_update()` row lock
  around a liveness re-read + publish; the `except` wraps that block (savepoint
  already rolled back → connection clean for `refresh_from_db`). Same lock guard
  added to `PostWriteView.delete`. Full two-thread harness omitted as flaky; the
  deterministic invariant test (a taken-down post is not resurrected) covers it.
- Type-hinted `submit_edit_for_moderation` (finding #12).

Verification (`--create-db`, Postgres local so `select_for_update` is real):
`19 passed` (edit_moderation + post_edit_delete), `143 passed` full package,
`14 passed` forum_host, `makemigrations --check` clean, `manage.py check` clean,
`spectacular --validate` clean (no forum schema errors).

### 2026-07-03 - Code review (code-review-orchestrator)

- **Applied (labeled HIGH, reviewer self-downgraded to MEDIUM):** `delete()`
  called `post.unpublish()` on the pre-lock read; `unpublish()` SAVES the row, so
  a concurrent trusted PATCH's field updates could be clobbered by stale values.
  Switched to `locked.unpublish()` (the fresh under-lock instance). Re-verified:
  157 forum tests still green.
- **Declined with reasoning (labeled MEDIUM, reviewer self-downgraded to LOW):**
  `workflow.py` uses `obj.get_workflow()/current_workflow_state/workflow.start(obj)`
  in the critical section rather than `locked`. These are pk/content-type/revision
  based and never SAVE `obj`'s stale mutable fields (the publish is revision-based),
  unlike `delete()`'s `unpublish()`. Switching would interleave `obj`/`locked`/
  `revision` in one block and reduce clarity for no correctness gain. `locked` is
  used exactly where staleness matters — the liveness re-read.
- All other findings were INFO/positives (transaction/except pattern correct,
  trust invariant maintained, no `apps.*` imports, migration correct).

### 2026-07-03 - Completed by completing-todos skill (run 2026-07-03-2006)

- Verification: all 6 acceptance criteria passed; 157 forum tests green (143
  package + 14 host), migrations/system/schema checks clean.
- Review: 8 findings (1 HIGH→MEDIUM, 1 MEDIUM→LOW, 6 INFO). 1 repaired
  (`locked.unpublish()`), 1 declined with reasoning (no correctness gain), rest
  informational. No unaddressed blocking findings.
- NOT deployed: forum write path (incl. these fixes) still needs Railway
  (backend) + Cloudflare (web) deploy to reach prod, per todo 231 / memory.
