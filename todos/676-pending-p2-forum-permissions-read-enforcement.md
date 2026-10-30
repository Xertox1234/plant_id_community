---
status: pending
priority: p2
issue_id: "676"
tags: [forum, forum-categories, backend, permissions, security]
dependencies: ["675"]
triage: ready
triaged: 2026-10-30
owner_decision: "Staff and forum moderators bypass a No Access grant and keep seeing every forum, as is_hidden staff handling does today. (owner, 2026-10-30)"
---

# Forum categories slice 11b: enforce forum read permissions everywhere (replaces is_hidden)

## Problem

Read permissions only matter if every read path honours them. Today one helper (`_visible_boards`) gates the API; several other paths reuse it.

## Findings

- Consumers of the visibility helper: `api/views.py:134-160`, `digest.py:160-165`, `mentions.py:86-88`, `quotes.py:46-52`, `api/notifications.py:28-57`; plus search and the live-updates socket (`visible_topics`).
- Rule from earlier audits: hidden content returns 404, never 403 (no existence leak).
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Replace the helper with a per-user `visible_forums(user)` honouring list/read grants; thread it through every consumer above, search, sitemaps, the live socket and notifications.
2. Migrate `is_hidden=True` forums to a 'No Access for everyone' grant set, then drop `is_hidden`.
3. Cache per user per request; keep query counts fixed.

## Technical Details

- Files listed in Findings plus `apps/forum_host/sitemaps.py` and the live-updates consumer.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [ ] Test per consumer: a user without read access gets 404 on topic, post, search hit, quote, mention, notification and digest entry; a permitted user sees them.
- [ ] Test: anonymous access follows the anonymous grants.
- [ ] Test: `is_hidden` forums remain invisible after the data migration.
- [ ] Test: fixed query counts on the index and topic list.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).

### 2026-10-30 - Owner decision

- The 2026-10-29 triage question was answered by the owner: Staff and forum moderators bypass a No Access grant and keep seeing every forum, as is_hidden staff handling does today.
