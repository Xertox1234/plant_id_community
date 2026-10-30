---
status: pending
priority: p3
issue_id: "672"
tags: [forum, forum-categories, backend, web, notifications]
dependencies: ["665"]
triage: needs-design
triaged: 2026-10-29
blocked_on: "The owner needs to define the levels and the delivery channels for a new-topic notification."
owner_decision: "owner question at triage; skipped per overnight orders (2026-10-29)"
---

# Forum categories slice 8: Watch / Track / Mute per forum

## Problem

Discourse lets a member watch, track or mute a category; phpBB lets members subscribe to a forum. We only have per-topic subscriptions.

## Findings

- Exists: topic-level `TopicSubscription` — `backend/packages/wagtail_forum/wagtail_forum/models/subscriptions.py:13`.
- Notification fan-out and digest: `notifications.py`, `digest.py`.
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Model `ForumSubscription(user, forum, level)` with levels watching (notify on every new topic), watching_first_post, muted.
2. New-topic notifications fan out to forum watchers (respecting blocks/mutes, quiet hours and preferences); muted forums are excluded from the digest and the recent-topics feed for that user.
3. Web: a level picker on the forum page.

## Technical Details

- `models/subscriptions.py`, `notifications.py`, `digest.py`, recent-topics view in `api/views.py`.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [ ] Test: a watcher gets one notification per new topic; the author does not notify themselves.
- [ ] Test: a muted forum's topics are absent from that user's digest and recent feed.
- [ ] Test: fan-out query count is bounded.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).
