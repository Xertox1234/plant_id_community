---
status: pending
priority: p3
issue_id: "683"
tags: [forum, forum-categories, wagtail, admin, owner-check]
dependencies: ["668"]
---

# Owner browser check: forum structure drag-and-drop tree (todo 668)

## Problem

Todo 668 shipped the drag-and-drop forum structure tree at `/cms/forum/forums/`, covered by automated tests. Its manual browser check was moved here by the owner (2026-10-29) so the slice could ship without it.

## Findings

- Re-pointed from todo 668, criterion 4.
- Only the owner can run and record this check.

## Proposed Solution

Open `/cms/forum/forums/` as staff. Drag a category, then a forum (including across categories), reload, and confirm the order is kept. Then use the up/down and Move buttons without the mouse.

## Acceptance Criteria

- [ ] Manual browser check recorded with date: drag, reload, order kept; keyboard alternative works.

## Work Log

- 2026-10-29: Created when todo 668's manual browser check was re-pointed here at the owner's request.
