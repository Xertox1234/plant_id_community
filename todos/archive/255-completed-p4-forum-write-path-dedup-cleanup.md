---
status: completed
priority: p4
issue_id: "255"
tags: [forum, maintainability, refactor]
dependencies: ["250", "251", "252"]
source_review: "docs/reviews/2026-07-02-2252-forum-write-path-trial.md"
source_finding: "12"
---

# Deduplicate the forum write path (visibility guard, permissions, serializers, trust routing)

## Context

Todo-244's review trial: the bundled reuse/simplification/efficiency/altitude
angles converged on a duplication cluster in the forum write path, re-verified
on main `d52cf14`. Finding #12. Deliberately sequenced AFTER todos 250–252
(same files; those fixes change the guards this refactor single-sources —
doing this first would create merge friction and 252 already extracts the
editability predicate).

## Problem

`W = backend/packages/wagtail_forum/wagtail_forum`

- **Visibility predicate ×3 shapes**: `PostWriteView._get_editable`
  (imperative if-chain, fetch-then-check = 2 queries),
  `ReactionToggleView.post` (same if-chain), and the list/detail views
  (single-query queryset filters). A visibility change must hit all of them;
  this is the audit-M6/M7 no-existence-leak predicate.
- **`get_permissions()` duplicated verbatim** (`W/api/views.py:134`, `:271`);
  the declarative `permission_classes = [IsAuthenticatedOrReadOnly]`
  expresses the same rule with nothing to keep in sync (host default is
  already IsAuthenticatedOrReadOnly).
- **`PostEditSerializer` is a byte-copy of `ReplyCreateSerializer`**
  (`W/api/serializers.py:301`, `:308`) — the body contract now lives in three
  serializers (TopicCreate repeats the pair).
- **Trust-routing core duplicated** between `submit_for_moderation` and
  `submit_edit_for_moderation` (`W/workflow.py`) — extract a shared
  `_route_revision_by_trust(obj, user)` (todo 250 touches this code first).
- **Redundant work**: PATCH does an unconditional `refresh_from_db` although
  the helper already refreshes (one wasted full-row SELECT per edit);
  `_get_editable`'s separate `_visible_boards().filter(...).exists()` doubles
  the visibility queries vs the single-fetch shape.
- **Guard-test altitude**: the host throttle guard test pins wrapper class
  identity only — a new unsafe method on a wrapped view ships unthrottled
  while the test stays green; iterate unsafe `http_method_names` instead.
- **Comment rot**: `_get_editable` cites "mirrors ReplyCreateView" — deleted
  in the same PR that added the comment.

## Recommended Action

After 250–252 land: extract `_get_visible_post(post_id)` (single query,
`select_related("topic", "author")`) used by PostWriteView and
ReactionToggleView; replace both `get_permissions` overrides with the
declarative attribute; make `PostEditSerializer` subclass
`ReplyCreateSerializer` (keeps a distinct OpenAPI component name); drop the
redundant refresh; strengthen the throttle guard test; fix the comment.
Pin query counts before/after (expect PATCH/DELETE to lose 2 queries each).

## Acceptance Criteria

- [x] One shared visible-post helper; grep shows no imperative copies left.
- [x] `get_permissions` overrides gone; auth behavior pinned by todo-253's
      401 tests.
- [x] Body-contract serializer declared once (subclass or mixin).
- [x] Trust-routing core exists once in workflow.py.
- [x] Query-count tests updated: PATCH/DELETE visibility queries reduced and
      pinned exactly (refresh part was already gone — see stale premise below).
- [x] Throttle guard test fails if an unsafe method lacks a rate.
- [x] Full forum suite green.

## Work Log

### 2026-07-02 - Created

- Filed from the todo-244 trial (finding #12), re-verified on main d52cf14.

### 2026-07-04 - Implemented + verified (run 2026-07-04-0200)

Dedup, done after 250-252 as sequenced. `W = packages/wagtail_forum/wagtail_forum`.

- **Shared visible-post helper**: `W/api/views._get_visible_post(post_id)` — a
  SINGLE query that folds the M6/M7 visibility guard into the fetch
  (`filter(live=True, topic__live=True, topic__board__in=_visible_boards())`).
  `PostWriteView._get_editable` now delegates to it (kept as a thin method so the
  hard-delete monkeypatch test's patch point survives); `ReactionToggleView.post`
  calls it too. Both imperative if-chains gone (grep-verified). Fixed the "mirrors
  ReplyCreateView" comment rot (item 7).
- **Declarative permissions**: both `get_permissions` overrides (TopicListView,
  PostListView) → `permission_classes = [IsAuthenticatedOrReadOnly]` (behaviour-
  identical; also the project default). Auth pinned by the existing
  `test_unauthenticated_writes_are_rejected` (POSTs both list endpoints → 401).
- **Body contract once**: `_ForumBodyContract` mixin (body field + validate_body);
  `TopicCreateSerializer`/`ReplyCreateSerializer` subclass it; `PostEditSerializer`
  subclasses `ReplyCreateSerializer` (kills the byte-copy, keeps a distinct
  OpenAPI component name).
- **Trust-routing once**: `W/workflow._route_revision_by_trust(obj, revision,
  trusted, *, cancel_stale=False)`. Both `submit_for_moderation` (create,
  `cancel_stale=False`) and `submit_edit_for_moderation` (edit, `cancel_stale=True`
  — the todo-250 wedge fix) call it. The flag keeps the create path from reading
  `obj.current_workflow_state` (a DB hit) → byte- AND query-identical there
  (advisor caught this; an unconditional cancel-if-exists would have added a query).
- **Query pins** (new — none existed): `test_delete_query_count_is_pinned` (==32),
  `test_edit_query_count_is_pinned` (==68). The bulk is Wagtail's
  publish/unpublish + counter-signal cascade (255 does not change it); the pin
  protects the visibility-fold delta.
- **Throttle guard**: `test_every_unsafe_handler_is_throttled` iterates each
  wrapper's actually-defined handlers and requires every unsafe one to be in the
  254 `_forum_throttled_methods` marker — so a new unrated unsafe handler fails
  (the class-identity test alone would stay green). search/sync (GET-only) pass
  trivially but gain protection.

**Stale premises (verified against current code, honestly logged):**
- The "unconditional `refresh_from_db` in PATCH" is ALREADY gone (removed in todo
  250's PR #435; `patch()` comments that the helper already refreshed). So the
  savings is ~1 query/op (the visibility fold), NOT 2 — the AC's "+refresh" half
  did not apply.

Verification:
- Workflow extraction gate: `pytest test_workflow_routing test_moderation_task
  workflow/test_edit_moderation test_integration` → **20 passed** (create + edit
  routing intact).
- Query pins + throttle guard → **3 passed** (32/68 hold; unsafe-handler guard green).
- Full forum suite `pytest packages/wagtail_forum/ apps/forum_host/` →
  **190 passed**.

### 2026-07-04 - Completed by completing-todos skill (run 2026-07-04-0200)

- Verification: all 7 acceptance criteria passed (20 workflow-gate + 3 pins/guard
  + 190 full forum suite; grep-verified no imperative copies / no get_permissions).
- Review: `code-review-orchestrator` — 0 CRITICAL/HIGH/MEDIUM, 0 blocking. All 8
  findings INFO confirmations across the 5 focus areas: workflow extraction
  behavior-preserving for BOTH paths (create never reads current_workflow_state;
  edit preserves cancel-stale-then-restart), `_get_visible_post` identical 404 set,
  serializer mixin no schema break, `IsAuthenticatedOrReadOnly` matches the old
  override, query pins load-bearing. Nothing to repair.

### 2026-07-04 - Started by completing-todos skill (run 2026-07-04-0200)

- Picked up by automated workflow.
