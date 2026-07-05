---
status: completed
priority: p3
issue_id: "252"
tags: [forum, api, web, bug]
dependencies: ["251"]
source_review: "docs/reviews/2026-07-02-2252-forum-write-path-trial.md"
source_finding: "8"
---

# Make can_edit/can_delete reflect the real write rules (affordance parity)

## Context

Todo-244's review trial verified (finding #8, re-confirmed on main `d52cf14`)
that `PostSerializer.get_can_edit/get_can_delete`
(`backend/packages/wagtail_forum/wagtail_forum/api/serializers.py:277-289`)
compute only the owner-or-moderator predicate, while `PostWriteView` also
rejects on opening-post (delete → 409) and closed/locked topic (edit → 409).
The PR-2b web UI gates its Edit/Delete buttons on exactly these flags
(PostCard), so users see actions that always fail. Depends on 251 because the
guard set it must mirror changes there (post.locked, DELETE topic guards).

## Problem

- `can_delete=true` is serialized for the topic author's opening post, but
  DELETE always 409s.
- `can_edit=true` is serialized for owned posts in closed/locked topics, but
  PATCH always 409s.
- The view comment claims the serializer "computes the same predicate" — the
  parity only covers the owner-or-mod half. Two hand-synced copies of the
  policy already diverged once; policy changes will diverge again.

## Recommended Action

Single-source the editability predicate — e.g. `Post.can_be_edited_by(user)`
/ `Post.can_be_deleted_by(user)` (or module-level helpers next to
`_visible_boards`) that encode owner-or-mod AND opening-post AND
closed/locked-topic AND (after 251) post.locked — used by BOTH
`PostWriteView._get_editable` and the serializer method fields. Watch the
query cost in list views: topic fields are already selected
(`select_related("topic")`) so the checks should add no queries (pin with
`assertNumQueries` per docs/rules/database.md).

## Acceptance Criteria

- [x] Serializer flags and view guards derive from one shared predicate.
- [x] Test: opening post serializes `can_delete=false` for its author.
- [x] Test: post in a closed (and separately locked) topic serializes
      `can_edit=false` for its author; moderator expectations tested.
- [x] Post-list query count pinned (no new N+1 from the shared predicate).
- [x] Full forum + web suites green (web PostCard behavior unchanged —
      it already consumes the flags).

## Work Log

### 2026-07-02 - Created

- Filed from the todo-244 trial (finding #8), re-verified on main d52cf14.

### 2026-07-04 - Started by completing-todos skill (run 2026-07-04-0200)

- Picked up by automated workflow.

### 2026-07-04 - Implemented (run 2026-07-04-0200)

Single-sourced the edit/delete policy so the serializer flags and the write
guards cannot diverge:

- `models/posts.py`: `Post.edit_block(user)` / `delete_block(user)` return
  `None` (allowed) or a `(code, message)` — the single source (owner-or-mod →
  per-post lock → frozen topic → [delete] opening-post). Thin `can_be_edited_by`
  / `can_be_deleted_by` booleans wrap them. Owner check is a short-circuit
  (`user.pk == author_id or has_perm`) so an author never triggers the
  permission lookup (keeps the list query flat).
- `api/serializers.py`: `get_can_edit`/`get_can_delete` now call the model
  booleans; removed the old `_is_owner_or_mod` (owner-only half).
- `api/views.py`: `_get_editable` is now the existence-404 gate only;
  `patch`/`delete` enforce policy via `_enforce_writable(post.edit_block/
  delete_block(user))` (forbidden→403, else→409). Every 251 status code + message
  is preserved. **Note: this unifies the PATCH frozen message to "Topic is closed
  or locked." — supersedes the 251 Work Log note that recorded the PATCH/DELETE
  message asymmetry as intentional (no test asserted the old PATCH string).**
- `api/views.py` `PostListView`: added `select_related("topic")` so the
  predicate's `obj.topic` read folds into the posts query (no N+1).

Tests (`tests/api/test_post_list.py`): `test_author_affordances_reflect_write_
rules` (opening post can_delete=false, reply true), `test_author_can_edit_false_
in_closed_topic` + `..._locked_topic` (per-operand), `test_moderator_affordance_
bypasses_post_lock` (mod sees can_edit=true on a locked post, author false),
`test_post_list_affordances_add_no_per_post_queries` (flat at 3 for an
authenticated author, N=20).

Verification:
- `pytest test_post_list.py test_post_edit_delete.py --reuse-db` → **27 passed**
  (flat-count pin == 3 held; all 251 codes/messages survived the view refactor).
- Full backend forum suite `pytest packages/wagtail_forum/ apps/forum_host/` →
  **170 passed**.
- Web forum tests (PostCard, ThreadDetailPage, forumMappers, forumService) →
  **76 passed** (flag contract unchanged; no web edits).

### 2026-07-04 - Code review disposition (run 2026-07-04-0200)

`code-review-orchestrator`: 2 HIGH, 1 MEDIUM, 2 LOW. Evidence-based dispositions:

- **HIGH #2 (posts.py "new per-post lock")** — FALSE ALARM. This is the todo-251
  lock check, *relocated* into `Post.edit_block` during single-sourcing, not a new
  constraint. Already reviewed clean in the 251 pass; documented in 251's work log,
  the code comments, and the model docstring. Flagged only as "new" vs pre-251 code.
- **HIGH #1 (refresh_from_db drops select_related cache → topic re-query)** —
  REAL but misrated. `submit_edit_for_moderation` (workflow.py:190) calls
  `obj.refresh_from_db()`, clearing the cache; `get_can_edit` then lazy-loads
  `obj.topic` on the PATCH response → exactly **+1 query on a single-object
  response** (the `author` lazy-load already existed there pre-252). Bounded, NOT
  an N+1 — the list path stays pinned at 3. The `get_can_edit` comment is already
  scoped ("in the list queryset"), so no misleading claim. Not blocking; handler's
  delicate concurrency logic left untouched.
- **MEDIUM (frozen message unified)** — intentional; see the Implemented note
  (supersedes 251's asymmetry note). No test asserted the old string.
- **LOW #1 (parity acid test missing)** — ADDRESSED. Added
  `test_affordance_flags_match_write_outcomes` and
  `test_affordance_flags_match_write_outcomes_in_closed_topic` to
  `test_post_edit_delete.py`: fetch the list flags, then assert the PATCH/DELETE
  endpoints agree (opening can_delete=false ⇔ DELETE 409; reply true ⇔ 200/204;
  closed-topic can_edit=false ⇔ PATCH 409). The strongest guard against future
  divergence — directly serves finding #8's goal.
- **LOW #2 (query-count test not exhaustive)** — SKIPPED (testing-the-test;
  marginal value, would require mutating source to prove).

Re-verified after adding the parity tests:
- `pytest test_post_edit_delete.py --reuse-db` → **19 passed**.
- Full backend forum suite → **172 passed**.

### 2026-07-04 - Completed by completing-todos skill (run 2026-07-04-0200)

- Verification: all 5 acceptance criteria passed (27→+2 parity targeted tests,
  172 full backend forum suite, 76 web forum tests).
- Review: 2 HIGH (1 false alarm = relocated 251 lock; 1 real-but-minor +1 query
  on single-object PATCH, not N+1), 1 MEDIUM (intentional message unification),
  2 LOW (1 addressed via parity acid tests, 1 skipped). None a genuine blocker on
  evidence-based evaluation.
