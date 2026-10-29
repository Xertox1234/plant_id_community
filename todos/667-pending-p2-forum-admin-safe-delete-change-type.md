---
status: pending
priority: p2
issue_id: "667"
tags: [forum, forum-categories, backend, wagtail, admin]
dependencies: ["666"]
triage: ready
triaged: 2026-10-29
owner_decision: "Forum↔category only: 667 builds forum↔category type changes; link conversions (forum→link, link→forum/category) move to todo 670 with the link URL field. The 'each type change' criterion covers forum↔category and category with forums refused (2026-10-29)"
---

# Forum categories slice 3: safe delete (move or delete topics) and change forum type

## Problem

Deleting a forum must never silently destroy topics (today's page-based board cascades). phpBB asks whether to move or delete content; phpBB also lets a forum change type with rules about its contents.

## Findings

- phpBB delete/type-change behaviour and its missing server-side target validation: `docs/superpowers/specs/2026-10-28-forum-categories-design.md` §2.
- Slice 1 sets `Topic.board` to PROTECT, so deletion currently fails rather than cascades.
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Delete flow for a forum: choose *move topics to [forum]* or *delete topics* (confirm with the topic count). Move runs in one transaction and updates counters on both sides; delete removes topics and their posts.
2. Delete flow for a category: must have no forums, or choose a target category to move its forums to.
3. Server-side validation of every target: exists, is a `forum` (for topics) / `category` (for forums), is not the item being deleted.
4. Change-type action: forum→category or forum→link requires the topics be moved or deleted first (same form); category→forum/link requires it has no forums; link→forum/category clears the URL.
5. Topic URL redirects for moved topics reuse `apps/forum_host/redirects.py`.

## Technical Details

- `wagtail_forum/admin/forums.py`, delete/convert views + templates, `apps/forum_host/redirects.py`.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [ ] Test: deleting a forum with *move* puts every topic in the target, counters correct on both forums, old topic URLs redirect.
- [ ] Test: deleting with *delete* removes topics and posts; no orphan rows.
- [ ] Test: target = self, a category, a link forum, or a non-existent id is rejected server-side.
- [ ] Test: a category with forums cannot be deleted without choosing a target category.
- [ ] Test: each type change enforces its rule and leaves no topics on a category or link.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).
