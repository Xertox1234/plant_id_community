---
status: pending
priority: p3
issue_id: "672"
tags: [forum, forum-categories, backend, web, notifications]
dependencies: ["665"]
triage: ready
triaged: 2026-11-01
blocked_on: "The owner needs to define the levels and the delivery channels for a new-topic notification."
owner_decision: "Discourse four levels: watching = every post (auto-subscribe each new topic), watching_first_post = new topics only, tracking = unread counts only, muted = hidden from Recent. New-topic alerts go to in-app + push, following the existing notification preference matrix; no new email. (owner, 2026-10-30) Tracking: store and select the level AND show per-forum unread badges on forum rows, built on the per-forum read markers from #1226 (todo 671). (owner, 2026-10-31) New-topic alert gets its OWN new_topic row in the push/in-app preference matrix (push on, in-app on, email off; also shown on the mobile settings card), not the reply row. A tracked forum's badge shows an unread COUNT, not just the has_unread dot. (owner, 2026-11-01)"
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

### 2026-10-30 - Owner decision

- The 2026-10-29 triage question was answered by the owner: Discourse four levels: watching = every post (auto-subscribe each new topic), watching_first_post = new topics only, tracking = unread counts only, muted = hidden from Recent. New-topic alerts go to in-app + push, following the existing notification preference matrix; no new email.

### 2026-10-31 - owner decision

- Owner answered the re-triage question: tracking is stored and selectable and also shows per-forum unread badges.
