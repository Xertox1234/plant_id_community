---
status: completed
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

- [x] Unauthenticated PATCH `/posts/{id}/` → 401 test exists and passes.
- [x] Unauthenticated DELETE `/posts/{id}/` → 401 test exists and passes.
- [x] `test_edit_on_locked_topic_conflicts` exists and passes.
- [x] Mutation check: makes the new 401 tests fail — **premise corrected** (see
      work log). Literal comment-out keeps 401 via the `IsAuthenticatedOrReadOnly`
      default; the real auth-hole mutation `permission_classes = []` fails them
      (403 ≠ 401). Intent (non-vacuous tests) met with evidence.
- [x] Full forum suite green.

## Work Log

### 2026-07-02 - Created

- Filed from the todo-244 trial (findings #9–#10), re-verified on main d52cf14.

### 2026-07-04 - Started by completing-todos skill (run 2026-07-04-0200)

- Picked up by automated workflow.

### 2026-07-04 - Implemented + verified (run 2026-07-04-0200)

Added to `tests/api/test_post_edit_delete.py` (no source changes — the guards
already exist; these pin them):

- `test_unauthenticated_patch_is_401`, `test_unauthenticated_delete_is_401` —
  anonymous PATCH/DELETE `/posts/{id}/` → 401 (finding #9). Mirror
  `test_unauthenticated_writes_are_rejected`.
- `test_edit_on_locked_topic_conflicts` — PATCH on a `topic.locked=True` topic →
  409, isolating the `locked` operand of the `is_closed or locked` guard that was
  only exercised via `is_closed` on the edit path (finding #10). No overlap with
  the 251 DELETE-operand tests.

**Mutation check — premise corrected (evidence-based).** The todo assumed
"deleting `permission_classes` would pass the suite (silent auth hole)". Empirical:
- **Mutation A** (comment out `permission_classes`) → 401 tests STILL PASS (2
  passed). The DRF default `DEFAULT_PERMISSION_CLASSES = [IsAuthenticatedOrReadOnly]`
  still blocks anonymous *writes* (PATCH/DELETE are unsafe methods), so bare
  removal does NOT open the endpoint. The finding's stated premise is wrong.
- **Mutation B** (`permission_classes = []`, no permission layer) → both 401
  tests FAIL (403 ≠ 401). So the tests ARE non-vacuous: they catch loss of the
  proper 401 auth-layer response. (Bonus: the response is 403, not 200 — the
  todo-252 `edit_block` rejects anonymous even with the DRF gate gone, i.e.
  defense-in-depth; the test pins the 401 layer specifically.)
- Reverted to `permission_classes = [IsAuthenticated]`; grep confirms no
  `MUTATION CHECK` markers remain.

Verification:
- `pytest test_post_edit_delete.py --reuse-db` → **22 passed** (19 + 3).
- Full backend forum suite `pytest packages/wagtail_forum/ apps/forum_host/` →
  **175 passed**.

### 2026-07-04 - Completed by completing-todos skill (run 2026-07-04-0200)

- Verification: all acceptance criteria passed (22 targeted + 175 full forum
  suite; mutation check done with corrected premise — see above).
- Review: `code-review-orchestrator` — 0 defects, 0 blocking. 2 INFO polish,
  both applied: (1) reworded the PATCH-401 comment (dropped the ViewSet-specific
  "gotcha #1" citation — `PostWriteView` is a plain `APIView`), (2) added a
  body-unchanged assertion to `test_unauthenticated_patch_is_401` for symmetry
  with the DELETE test. Re-verified: 4 passed.
