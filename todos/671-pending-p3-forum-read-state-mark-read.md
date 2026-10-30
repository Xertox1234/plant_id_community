---
status: pending
priority: p3
issue_id: "671"
tags: [forum, forum-categories, backend, web]
dependencies: ["665"]
triage: ready
triaged: 2026-10-29
---

# Forum categories slice 7: per-forum unread markers, mark forum read, mark all forums read

## Problem

phpBB shows an unread marker per forum and offers 'mark forum read' and 'mark all forums read'. We have per-topic read state only.

## Findings

- Exists: per-topic reads `backend/packages/wagtail_forum/wagtail_forum/models/topic_reads.py`; unread annotation `api/views.py:197-230` using `ForumProfile.read_watermark_at` (`models/profiles.py:138`).
- Missing: nothing advances `read_watermark_at` after profile creation — its only writers are creation defaults (`models/profiles.py:188`, `signals.py:175`), verified 2026-10-28 — so there is no mark-all-read; no per-forum read mark.
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Add a per-user per-forum mark (`ForumRead(user, forum, marked_at)`), used as a floor in the unread annotation alongside the global watermark.
2. Endpoints: mark one forum read; mark all read (advances `read_watermark_at`).
3. Forum rows and category rows report `has_unread` (any visible topic newer than the user's effective floor), with a bounded query count.
4. Web: unread dot on forum rows, 'Mark forum read' on the forum page, 'Mark all read' on the index.

## Technical Details

- `models/topic_reads.py`, `api/views.py` `_annotate_topic_unread`, new endpoints, web index + thread list.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [ ] Test: marking a forum read clears its topics' unread flags and not other forums'.
- [ ] Test: mark all read advances the watermark and clears every forum.
- [ ] Test: anonymous users get no unread markers and the endpoints require auth.
- [ ] Test: the index unread computation has a fixed query count.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).

### 2026-10-28 - Advisor review of the spec

- Amended after an advisor review of the spec (slug constraint, page-row deletion order, link-type placement, Flutter list filter, naming).
