---
status: pending
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

- [ ] One shared visible-post helper; grep shows no imperative copies left.
- [ ] `get_permissions` overrides gone; auth behavior pinned by todo-253's
      401 tests.
- [ ] Body-contract serializer declared once (subclass or mixin).
- [ ] Trust-routing core exists once in workflow.py.
- [ ] Query-count tests updated: PATCH/DELETE visibility+refresh queries
      reduced and pinned exactly.
- [ ] Throttle guard test fails if an unsafe method lacks a rate.
- [ ] Full forum suite green.

## Work Log

### 2026-07-02 - Created

- Filed from the todo-244 trial (finding #12), re-verified on main d52cf14.
