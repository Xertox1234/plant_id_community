---
status: pending
priority: p3
issue_id: "253"
tags: [forum, testing]
dependencies: []
source_review: "docs/reviews/2026-07-02-2252-forum-write-path-trial.md"
source_finding: "9"
---

# Fill the forum write-endpoint test gaps (401 coverage, locked-guard operand)

## Context

Todo-244's review trial: the custom test-quality reviewer surfaced two
coverage gaps in the forum write tests, both adversarially CONFIRMED and
re-verified on main `d52cf14` (grep: zero `401`/unauthenticated hits in
`test_post_edit_delete.py`; zero `locked` hits there). Findings #9–#10.
Independent of todos 250–252 (these tests pin guards that already exist).

## Problem

1. **No unauthenticated 401 test for PATCH/DELETE `/posts/{id}/`** (#9):
   `test_unauthenticated_writes_are_rejected` (test_topic_create.py) covers
   only the POST endpoints; every PATCH/DELETE test `force_authenticate`s
   first. Deleting `permission_classes = [IsAuthenticated]` from
   `PostWriteView` would pass the entire suite — the exact silent-auth-hole
   class CLAUDE.md gotcha #1 warns about.
2. **`locked=True` operand untested on the edit path** (#10): the PATCH guard
   is `topic.is_closed or topic.locked` but only `is_closed` is exercised
   (the reply path tests both operands). Removing `or topic.locked` would
   pass the suite.

## Recommended Action

In `backend/packages/wagtail_forum/wagtail_forum/tests/api/test_post_edit_delete.py`:

- Add unauthenticated PATCH and DELETE against `/posts/{id}/` asserting 401
  (extend or mirror the existing `test_unauthenticated_writes_are_rejected`
  shape).
- Add `test_edit_on_locked_topic_conflicts`: set `topic.locked = True`
  (mirror the closed-topic test's `queryset.update(...)` shape to avoid
  re-triggering moderation), PATCH, assert 409.

## Technical Details

- `force_login()`/fixtures: omit `password=` kwargs (docs/rules/testing.md —
  detect-secrets gate).
- Backend tests run via pytest; changing the app subset needs `--create-db`
  (docs/rules/testing.md).
- If todo 251 lands first, its new DELETE-guard tests may partially overlap —
  dedup rather than duplicate.

## Acceptance Criteria

- [ ] Unauthenticated PATCH `/posts/{id}/` → 401 test exists and passes.
- [ ] Unauthenticated DELETE `/posts/{id}/` → 401 test exists and passes.
- [ ] `test_edit_on_locked_topic_conflicts` exists and passes.
- [ ] Mutation check: commenting out `permission_classes` on `PostWriteView`
      (locally, not committed) makes the new 401 tests fail.
- [ ] Full forum suite green.

## Work Log

### 2026-07-02 - Created

- Filed from the todo-244 trial (findings #9–#10), re-verified on main d52cf14.
