---
status: pending
priority: p2
issue_id: "677"
tags: [forum, forum-categories, backend, web, permissions, security]
dependencies: ["676"]
triage: ready
triaged: 2026-10-29
---

# Forum categories slice 11c: enforce post/reply/poll/attach permissions and reflect them in the web UI

## Problem

Write permissions per forum (phpBB f_post, f_reply, f_poll, f_attach) must be enforced on every write path and reflected in the UI.

## Findings

- Write paths: topic create (`api/views.py` `_create_topic`), post create, poll create (`api/polls.py`), image upload (`api/image_management.py`).
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Enforce each flag server-side (403 with a stable error code when the forum is visible but the action is not allowed).
2. API returns the viewer's capabilities per forum (`can_post`, `can_reply`, `can_poll`, `can_attach`).
3. Web hides/disables the composer, reply box, poll and attachment controls accordingly.

## Technical Details

- `api/views.py`, `api/polls.py`, `api/image_management.py`, web composer components.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [ ] Test per flag: denied returns 403 with the error code; allowed succeeds.
- [ ] Web Vitest: controls hidden/disabled from capabilities.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).
