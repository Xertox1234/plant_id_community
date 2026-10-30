---
status: pending
priority: p4
issue_id: "673"
tags: [forum, forum-categories, web, backend]
dependencies: ["665"]
triage: ready
triaged: 2026-10-29
---

# Forum categories slice 9: collapsible categories remembered per user

## Problem

phpBB's official collapsible-categories extension lets members collapse a category header; state is stored per user (cookie for guests).

## Findings

- `docs/superpowers/specs/2026-10-28-forum-categories-design.md` §2 (extension stores in DB for users, cookie for guests).
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Store collapsed category ids on the user's forum preferences (existing `notification_preferences`-style JSON or a small model); guests use localStorage.
2. Web: chevron on each category header, accessible (`aria-expanded`).

## Technical Details

- `models/profiles.py` / `preferences.py`, web `CategoryListPage.tsx`.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [ ] Test: collapsing persists across sessions for a signed-in user.
- [ ] Web Vitest: toggle hides forums, `aria-expanded` flips, guest state survives reload.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).
