---
status: pending
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

- [ ] A test asserts the acting moderator (not `None`/system) is attributed
      in `ModelLogEntry` after `ForumUnpublishBulkAction` runs
- [ ] A test asserts unauthenticated `POST` to the report endpoint returns
      401
- [ ] Both new tests are non-vacuous: the mutations described in
      Recommended Action step 3 make them fail
- [ ] Full `wagtail_forum` + `forum_host` suite green

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

## Notes

p3 — both are coverage gaps on already-verified-correct, merged, CI-green
code, not live defects. Same shape as archived todo 253
(`forum-write-endpoint-test-gaps`), also filed as p3 for the identical
reason. No `source_review`/`source_finding` frontmatter: this finding didn't
come from a `docs/reviews/` or `docs/audits/` doc, it came from an ad hoc
orchestrator dispatch during todo 254's archival — provenance is recorded
above and in todo 254's Work Log instead.
