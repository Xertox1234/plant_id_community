---
status: pending
priority: p3
issue_id: "670"
tags: [forum, forum-categories, backend, web]
dependencies: ["666"]
---

# Forum categories slice 6: link forums with click tracking

## Problem

phpBB link forums are rows on the index that redirect to a URL, optionally counting clicks.

## Findings

- `docs/superpowers/specs/2026-10-28-forum-categories-design.md` §2 (FORUM_LINK; phpBB stores clicks in the post counter — use a dedicated field).
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Add the `link` option to the todo-666 admin form. Fields: `link_url` (http/https only, validated), `track_clicks`, `click_count`.
2. Endpoint `/forum/links/{id}/go/` that increments atomically (`F()`) and 302s; untracked links render the URL directly with `rel="noopener nofollow"`.
3. Link forums never accept topics (API 400/404) and never appear as move targets.

## Technical Details

- New view in `api/views.py` or a host redirect view; web forum row component.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [ ] Test: tracked click increments once per request and redirects; `javascript:` and other schemes rejected at save.
- [ ] Test: creating a topic in a link forum is refused.
- [ ] Test: link forums never appear in `GET /forum/boards/` (Flutter would fetch `/topics/` on them).
- [ ] Test: the admin form offers `link` and requires a valid URL for it.
- [ ] Web Vitest: link rows render as external links with a click count when tracked.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).

### 2026-10-28 - Advisor review of the spec

- Amended after an advisor review of the spec (slug constraint, page-row deletion order, link-type placement, Flutter list filter, naming).
