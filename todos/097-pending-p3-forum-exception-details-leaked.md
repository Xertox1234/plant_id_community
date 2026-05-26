---
status: pending
priority: p3
issue_id: "097"
tags: [forum, backend, security]
dependencies: []
source_review: "docs/superpowers/plans/2026-05-25-forum-phase2-security.md"
source_finding: "M1"
---

# Forum: replace `str(e)` error responses with generic messages

## Problem

Four forum endpoints return `str(e)` in JSON 500 responses, leaking internal exception details (stack frames, file paths, ORM error strings) to clients in production.

## Findings

From security-reviewer audit 2026-05-26:

- `api_views.py:121` — `all_topics_list` except block
- `api_views.py:327` — `forum_ai_assist` except block
- `api_views.py:561` — `PostReactionView` except block
- `api_views.py:1102` — `user_trust_level` except block

## Recommended Action

Replace `str(e)` in each Response payload with a generic `"An error occurred."` string. Log the real exception server-side with `logger.exception(...)` before returning. No behavior change to callers.

## Acceptance Criteria

- [ ] All four locations return a generic error message (not `str(e)`) to clients.
- [ ] Each replaced location logs the real exception via `logger.exception`.
- [ ] `python manage.py test apps.forum_integration --noinput` still green.

## Work Log

### 2026-05-26 - Created

- Surfaced by security-reviewer during Phase 2 audit (MEDIUM — out of scope for Phase 2).
