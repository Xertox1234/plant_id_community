---
status: in_progress
priority: p3
issue_id: "265"
tags: [forum, testing, moderation]
dependencies: []
---

# Forum moderation test-coverage gaps: bulk-unpublish attribution, report 401

## Problem

A retrospective `code-review-orchestrator` pass on the merged todo-254
moderation epic (run during its archival) surfaced two test-coverage gaps.
Neither is a live defect — both confirmed the underlying code is already
correct — but two security/attribution-relevant behaviors ship with no
regression test pinning them.

## Findings

- **HIGH** (cross-cutting-reviewer) —
  `test_bulk_unpublish_action_unpublishes_selected_posts`
  (`backend/packages/wagtail_forum/wagtail_forum/tests/test_admin.py:270`)
  only asserts `post.live is False`; it never asserts the acting moderator
  lands in `ModelLogEntry`. `ForumUnpublishBulkAction.get_execution_context()`
  (`wagtail_hooks.py`) overrides `user=self.request.user` specifically to
  avoid attributing takedowns to "the system" instead of the acting
  moderator (per its own docstring, added in todo-254 Slice 4) — but that
  override has no regression test.
  `tests/test_actor_attribution.py` is the established pattern for this bug
  class (audit finding M15: API-driven publish/unpublish must attribute the
  acting user) and was never extended to the new bulk-unpublish path.
- **MEDIUM** (cross-cutting-reviewer) — no test asserts that an
  unauthenticated `POST /forum/posts/<id>/reports/` returns 401
  (`backend/packages/wagtail_forum/wagtail_forum/tests/api/test_reports.py:38`),
  unlike every other unsafe-write endpoint in the suite (topic create, reply
  create, reaction toggle, post edit/delete, image upload all have this
  case). `PostReportView` is the one new unsafe-write handler todo-254 added
  and the one missing this coverage.

## Recommended Action

1. Add an attribution assertion to (or alongside)
   `test_bulk_unpublish_action_unpublishes_selected_posts`: after the bulk
   action runs, fetch the `ModelLogEntry` for one unpublished post
   (`action="wagtail.unpublish"`, latest by timestamp) and assert
   `.user == admin`. Mirror
   `test_actor_attribution.py::test_api_delete_unpublish_logs_acting_user`.
2. Add an unauthenticated-401 case for the report endpoint in
   `test_reports.py` (or extend
   `test_topic_create.py::test_unauthenticated_writes_are_rejected`'s
   pattern to include it).
3. Per `docs/rules/testing.md`'s non-vacuous-mutation rule, verify each new
   test actually catches the regression it claims to: for the 401 test,
   mutate `PostReportView.permission_classes` to `AllowAny` (not delete it —
   `IsAuthenticatedOrReadOnly` is the DRF default and would mask a deleted
   `permission_classes`, producing a false-pass); for the attribution test,
   temporarily drop the `get_execution_context()` override and confirm the
   test fails.

## Technical Details

- `backend/packages/wagtail_forum/wagtail_forum/wagtail_hooks.py` —
  `ForumUnpublishBulkAction.get_execution_context()`
- `backend/packages/wagtail_forum/wagtail_forum/tests/test_admin.py:270`
- `backend/packages/wagtail_forum/wagtail_forum/tests/test_actor_attribution.py`
  — pattern to mirror
- `backend/packages/wagtail_forum/wagtail_forum/api/views.py` —
  `PostReportView`
- `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_reports.py:38`
- `docs/rules/testing.md` — non-vacuous mutation-check rule

## Acceptance Criteria

- [x] A test asserts the acting moderator (not `None`/system) is attributed
      in `ModelLogEntry` after `ForumUnpublishBulkAction` runs
- [x] A test asserts unauthenticated `POST` to the report endpoint returns
      401
- [ ] Both new tests are non-vacuous: the mutations described in
      Recommended Action step 3 make them fail — **partially true, see
      "Cannot honestly flip" note in Work Log**: the 401 test's mutation
      (`permission_classes` → `AllowAny`) does make it fail, verified. The
      attribution test's prescribed mutation (dropping the
      `get_execution_context()` override) does NOT make it fail — root
      cause identified, not a defect in the test or the code.
- [x] Full `wagtail_forum` + `forum_host` suite green

## Work Log

### 2026-07-13 - Created from todo-254 retrospective review

- Filed from a `code-review-orchestrator` retrospective checklist pass
  (cross-cutting-reviewer) dispatched against the merged todo-254 epic diff
  during its archival. 4 reviewers, 9 total findings; these 2 (HIGH +
  MEDIUM) were the only genuinely new and actionable ones — the rest were
  pre-existing-pattern repeats or already in pending todo 259's scope. Full
  review context lives in
  `todos/archive/254-completed-p1-forum-moderation-safety-admin.md`'s Work
  Log.

### 2026-07-13 - Started by completing-todos skill (run 2026-07-13-0237)

- Picked up by automated workflow.
- Independently verified both findings are pure coverage gaps before writing
  any test, per the todo's own claim: `grep`-confirmed
  `PostReportView.permission_classes = [IsAuthenticated]`
  (`api/views.py:651`) is already correct, and read
  `ForumUnpublishBulkAction.get_execution_context()`
  (`wagtail_hooks.py:186-191`) — it already overrides `user=self.request.user`
  and threads it through `execute_action`. No code fix needed for either.
- Added `test_unauthenticated_report_is_rejected` to `test_reports.py`,
  mirroring `test_topic_create.py::test_unauthenticated_writes_are_rejected`'s
  pattern. Mutation check (Recommended Action step 3): mutated
  `PostReportView.permission_classes` to `[AllowAny]` — first attempt caused
  a `NameError` (forgot the import), which I caught and did NOT count as
  proof; redid it with the import added, and the test correctly failed with
  `assert 400 == 401` (a real behavioral difference, not a crash). Restored
  the file from a pre-mutation backup and reran the full `test_reports.py` +
  `test_admin.py` suite (22 passed) to confirm a clean revert.
- Added the attribution assertion to
  `test_bulk_unpublish_action_unpublishes_selected_posts` in `test_admin.py`,
  mirroring `test_actor_attribution.py::test_api_delete_unpublish_logs_acting_user`.
  It passes: `entry.user == admin` for the `wagtail.unpublish` `ModelLogEntry`.

#### Cannot honestly flip: attribution test's prescribed mutation doesn't fail it

Per the todo's Recommended Action step 3, I mutated
`ForumUnpublishBulkAction.get_execution_context()` to drop the
`"user": self.request.user` override (`return super().get_execution_context()`
instead), expecting the attribution assertion to fail. **It did not — the
test still passed** (`entry.user == admin`, unchanged).

Root-caused via primary sources, not guessed:

- `wagtail/admin/auth.py::require_admin_access` (the decorator wrapping
  every Wagtail admin view, including this bulk action — `BulkAction` is a
  Django `FormView` dispatched through the normal admin URL conf) does
  `with LogContext(user=user): return get_localized_response(...)` for the
  whole view.
- `wagtail/log_actions.py::LogActionRegistry.log()` line 164:
  `user = user or get_active_log_context().user` — when no explicit user is
  passed to `log()`, it falls back to the currently-active `LogContext`'s
  user.
- `UnpublishAction._unpublish_object()` passes `user=self.user` straight
  through to `log()`. So even with the override removed (`self.user` ends up
  `None` for this call), `log()`'s fallback picks up the SAME admin user from
  the ambient `LogContext` that `require_admin_access` already activated for
  this request.

Conclusion: `get_execution_context()`'s explicit override is **redundant on
this specific code path** — any bulk-unpublish action running inside a
normal Wagtail admin view gets correct attribution automatically, override
or not. This is NOT true for the DRF API path (`test_actor_attribution.py`'s
own docstring: "Wagtail's LogContext only activates inside admin views, so
the DRF paths must pass the user explicitly") — which is presumably why the
todo-254 author added the override in the first place, most likely by
correctly generalizing the DRF-path lesson to a path where it turned out not
to be strictly necessary. The override is still correct and harmless; I did
not remove it (out of scope, no reason to touch working code that costs
nothing).

**What this means for the test**: it is not vacuous in the "passes no
matter what" sense — a genuinely wrong (but truthy) user value, or a real
regression to `LogContext` itself, would still fail it. But it does not
specifically pin `get_execution_context()`'s override the way the HIGH
finding intended, because Wagtail's own fallback makes that override
unfalsifiable-by-omission on this path. I could not find a way to make the
*prescribed* mutation (dropping the override) fail the test without
manufacturing an unrealistic scenario (e.g. asserting a deliberately wrong
user, which proves the assertion is live but not that the override is
load-bearing) — advisor confirmed this is a discovery about the code's
actual behavior, not a defect in the test, and that I should not force the
box or invent an artificial mutation to make it "pass."

- Verification: `pytest packages/wagtail_forum/ apps/forum_host/ -q` → 265
  passed, 0 failed (criterion 4 met).

### 2026-07-13 - Skipped by completing-todos skill (run 2026-07-13-0237)

- Presented the "Cannot honestly flip" finding above to the user (3/4
  acceptance criteria cleanly met; the 4th is genuinely half-true, not
  fakeable per Safety Rail #4 — "no --force-complete"). User chose: skip,
  leave in_progress.
- Both new tests (`test_bulk_unpublish_action_unpublishes_selected_posts`'s
  attribution assertion, `test_unauthenticated_report_is_rejected`) and the
  full-suite green state are already in place and will NOT be reverted —
  only the archival step is deferred. A future session (or this todo's
  eventual closer) has two honest options: (a) accept that the override is
  redundant-but-harmless on this path and mark criterion 3 done with this
  Work Log as the record, since the ACTUAL underlying behavior (attribution
  works) is proven, just not via the specific mechanism assumed; or (b)
  write a differently-shaped test that pins the override more directly
  (e.g. asserting `get_execution_context()`'s return value directly,
  rather than the end-to-end `ModelLogEntry` behavior) if pinning the
  override itself (not just the outcome) is judged worth the extra test.
- Left in `in_progress` state (filename unchanged) per the skill's
  skip-todo protocol; NOT moved to `todos/archive/`.

## Notes

p3 — both are coverage gaps on already-verified-correct, merged, CI-green
code, not live defects. Same shape as archived todo 253
(`forum-write-endpoint-test-gaps`), also filed as p3 for the identical
reason. No `source_review`/`source_finding` frontmatter: this finding didn't
come from a `docs/reviews/` or `docs/audits/` doc, it came from an ad hoc
orchestrator dispatch during todo 254's archival — provenance is recorded
above and in todo 254's Work Log instead.
