---
status: pending
priority: p4
issue_id: "680"
tags: [forum, forum-categories, backend, web, security]
dependencies: ["676"]
triage: ready
triaged: 2026-10-29
owner_decision: "owner question at triage; skipped per overnight orders (2026-10-29)"
---

# Forum categories slice 14: password-protected forums

## Problem

phpBB can protect a forum with a password, unlocked per session. phpBB's own ACP recommends permissions instead; the owner wants parity.

## Findings

- `docs/superpowers/specs/2026-10-28-forum-categories-design.md` §2 (forums_access per session; last-post subject hidden while locked).
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Field `password_hash` (Django hasher); unlock endpoint stores the unlocked forum id in the session (rate-limited, 429 on abuse).
2. While locked: forum row visible with a lock, topics/last-post subject hidden, search/digest/notifications exclude it for that user.
3. Staff and forum moderators bypass.

## Technical Details

- Hooks into the `visible_forums(user)` helper from slice 11b; rate limiting per `backend/docs/patterns/architecture/rate-limiting.md`.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [ ] Test: locked forum hides topics until unlocked; wrong password counts toward the rate limit and returns 429 when exceeded.
- [ ] Test: unlock lasts for the session only.
- [ ] Test: search, digest and notifications exclude a locked forum.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).
