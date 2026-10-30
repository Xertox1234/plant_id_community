---
status: pending
priority: p4
issue_id: "679"
tags: [forum, forum-categories, backend, celery, cron]
dependencies: ["666"]
triage: ready
triaged: 2026-10-29
owner_decision: "owner question at triage; skipped per overnight orders (2026-10-29)"
---

# Forum categories slice 13: per-forum auto-pruning

## Problem

phpBB can prune old topics per forum on a schedule (days since last post / since viewed, optionally sparing polls, announcements and pinned topics).

## Findings

- `docs/superpowers/specs/2026-10-28-forum-categories-design.md` §2 (phpBB prune settings).
- Nightly cron service already exists (`forum-prune-cron`, see root CLAUDE.md `FORUM_LINK_PREVIEWS_ENABLED`).
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Fields: `prune_enabled`, `prune_days_since_last_post`, `prune_days_since_viewed` (optional), `prune_pinned` (default no), `prune_polls` (default no).
2. Management command `prune_forums --dry-run`, run from the nightly cron; prune = unpublish (soft) first, matching existing take-down semantics, with a log line per forum.
3. Admin *Pruning* tab.

## Technical Details

- New management command in `wagtail_forum/management/commands/`, `.railway/railway.ts` cron schedule if needed.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [ ] Test: only topics past the threshold are pruned; pinned/poll topics spared by default; `--dry-run` changes nothing.
- [ ] Test: disabled forums are untouched.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).
