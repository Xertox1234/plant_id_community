---
status: pending
priority: p3
issue_id: "674"
tags: [forum, forum-categories, backend, web, wagtail, moderation]
dependencies: ["666"]
triage: needs-design
triaged: 2026-10-29
blocked_on: "A design choice on how forum moderators get access and get scoped across Wagtail admin and the API"
owner_decision: "owner question at triage; skipped per overnight orders (2026-10-29)"
---

# Forum categories slice 10: per-forum moderators and a 'Moderators:' line

## Problem

phpBB assigns moderators per forum and lists them on each forum row. Today moderation rights are global Wagtail model permissions.

## Findings

- Global moderation check: `backend/packages/wagtail_forum/wagtail_forum/admin_views.py:305` `user_can_moderate_pending`.
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Model `ForumModerator(forum, user | group)`; admin *Moderators* tab on the forum.
2. A forum moderator may moderate (pending queue, reports, hide/lock/pin/move) only in their forums; global moderators unchanged.
3. API exposes moderators for the forum row; web shows 'Moderators: …'.

## Technical Details

- `admin_views.py` moderation queue filters, report actions, `api/views.py` moderation endpoints.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [ ] Test: a forum moderator can act on a topic in their forum and is refused in another forum.
- [ ] Test: the moderation queue shows a forum moderator only their forums' items.
- [ ] Web Vitest: moderators line renders.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).
