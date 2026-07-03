---
status: pending
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

- [ ] Regression test: flagged edit then clean edit on the SAME post — clean
      edit gets screened (published or genuinely pending), not wedged.
- [ ] Test: moderator PATCH on an author-deleted (author=None) post succeeds
      (redaction persists) or returns an explicit error — never a silent 200.
- [ ] Test: an exception before `save_revision` does NOT return 200 "pending".
- [ ] `moderation_decided` fires for edit outcomes (test with a signal receiver).
- [ ] Race either fixed with a locking test or explicitly re-verified and
      documented as not reproducible.
- [ ] Full forum suite green (`pytest` — see docs/rules/testing.md re: pytest
      runner and `--create-db` when changing app subsets).

## Work Log

### 2026-07-02 - Created

- Filed from the todo-244 trial (findings #1–#4, #13), re-verified on main
  d52cf14 before filing.
