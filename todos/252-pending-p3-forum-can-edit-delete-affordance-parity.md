---
status: pending
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

- [ ] Serializer flags and view guards derive from one shared predicate.
- [ ] Test: opening post serializes `can_delete=false` for its author.
- [ ] Test: post in a closed (and separately locked) topic serializes
      `can_edit=false` for its author; moderator expectations tested.
- [ ] Post-list query count pinned (no new N+1 from the shared predicate).
- [ ] Full forum + web suites green (web PostCard behavior unchanged —
      it already consumes the flags).

## Work Log

### 2026-07-02 - Created

- Filed from the todo-244 trial (finding #8), re-verified on main d52cf14.
