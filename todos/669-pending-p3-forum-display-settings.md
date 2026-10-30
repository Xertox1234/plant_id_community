---
status: pending
priority: p3
issue_id: "669"
tags: [forum, forum-categories, backend, web, wagtail]
dependencies: ["666"]
triage: ready
triaged: 2026-10-30
blocked_on: "An owner choice on the rules format (plain text, limited rich text, rules_url, or text plus link like phpBB) and the icon format (emoji or a named icon)"
owner_decision: "Rules: plain text plus an optional rules URL (phpBB style). Icon: a single emoji. Colour: chosen from the existing Canopy accent tokens (dark-mode safe). (owner, 2026-10-30) Open: a new question raised at the 2026-10-30 re-triage; skipped per overnight orders (2026-10-30)"
---

# Forum categories slice 5: per-forum display settings (locked, rules, icon/colour/image, topics per page, default sort)

## Problem

phpBB forums carry status and display settings; Discourse adds colour/icon and a default sort. None exist per board today.

## Findings

- Field list: `docs/superpowers/specs/2026-10-28-forum-categories-design.md` §2 (phpBB *Forum settings*, Discourse colour/icon/default sort/read-only banner).
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Fields: `is_locked` (no new topics or replies; staff exempt), `rules` (plain/limited rich text) or `rules_url`, `icon`, `colour` (validated against Canopy-safe tokens), optional image, `topics_per_page` (0 = default), `default_sort` (one of the existing `?sort=` values).
2. Admin: a *Display* and *Rules* tab.
3. API: expose the fields; enforce locked on topic/post create (403 with a clear code).
4. Web: colour/icon on category headers and forum rows, rules panel on the forum page, locked badge + disabled composer, page size and default sort honoured.

## Technical Details

- `api/views.py` create paths, `api/pagination.py` (default sort), web `CategoryListPage.tsx`, `ThreadListPage.tsx`, `NewThreadPage.tsx`.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [ ] Test: posting to a locked forum returns 403 for members and succeeds for staff.
- [ ] Test: `topics_per_page` and `default_sort` change the topic list response.
- [ ] Test: invalid colour values are rejected.
- [ ] Web Vitest: rules panel, locked state, colour/icon rendered.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).

### 2026-10-30 - Owner decision

- The 2026-10-29 triage question was answered by the owner: Rules: plain text plus an optional rules URL (phpBB style). Icon: a single emoji. Colour: chosen from the existing Canopy accent tokens (dark-mode safe).
