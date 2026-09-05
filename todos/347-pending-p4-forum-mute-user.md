---
status: pending
priority: p4
issue_id: "347"
tags: [forum, social, package, web]
dependencies: []
---

# Mute user — silence notifications/content without a hard block

## Problem

`UserBlock` is a hard, reciprocal-suppression block: it hides mentions,
replies, DMs, and public-profile activity in **both directions**
(`wagtail_forum/models/user_blocks.py:1-85`). There is no lighter "I just
don't want to see/hear this person" option — the Discourse "mute". Users
who don't want to escalate have no middle tool.

## Findings

- Block behavior today: DMs refuse with 403; mentions/replies suppressed;
  profile activity filtered (2026-09-04 backend catalog §4.6).
- A mute is materially different and simpler: **one-directional**, hides
  the muted user's posts/notifications for the muter only, does NOT block
  DMs... or does it? Decision point below.
- Web UI precedent exists: block/unblock controls in `PostCard.tsx:423-451`,
  `UserProfilePage.tsx:168-205`, `SettingsPage.tsx:60-132`.

## Recommended Action

1. **Package (`wagtail_forum`):** `UserMute(user, muted_user)` model,
   unique per pair, `FOR😯UM_MUTE_*` not needed — reuse block table shape.
   Add mute checks to the same centralized filters as blocks:
   `_visible_boards()`-adjacent topic/post filtering (muted author's
   content hidden from the muter), notification fan-out suppression in
   `wagtail_forum/notifications.py`, and serializer-level `is_muted` flag
   for the UI.
   - **Decision to record in Work Log:** whether mute silences DM sends for
     the muter (recommended: yes — a muted user's DMs land in a collapsed
     state or are refused softly). Discourse precedent: muted users' DMs
     still arrive; blocked users' don't. Match that unless there's a reason.
2. **API:** `POST/DELETE /users/<username>/mute/`, list on `me/blocks/`-
   style endpoint (`me/mutes/`) — mirrors `api/user_blocks.py:1-106`.
3. **Web:** mute action in the same menus as block; muted users list beside
   blocked users in Settings.
4. **Flutter:** deferred to the parity epic (341) rather than built twice.

## Technical Details

- Follow the block implementation closely — same auth, idempotency, and
  rate-limit wrapping (`apps/forum_host/api.py:28-193`,
  `DEFAULT_FORUM_RATELIMITS` in `apps/forum_host/constants.py:15-91`).
- Anything block-aware today should be enumerated and a decision recorded
  per site: search results, similar topics, experts rail, polls votes
  display, home activity feed.

## Acceptance Criteria

- [ ] Package model + endpoints + tests (one-directional: the muted user
      can still see the muter; verify explicitly)
- [ ] Muted authors excluded from muter's notification fan-out and content
      surfaces (test-pinned, including search)
- [ ] Web UI: mute/unmute + settings list
- [ ] DM behavior decision recorded and test-pinned

## Work Log

### 2026-09-04 - Filed

- Surfaced by the 2026-09-04 forum competitive assessment (smaller-misses:
  "mute-without-block").
