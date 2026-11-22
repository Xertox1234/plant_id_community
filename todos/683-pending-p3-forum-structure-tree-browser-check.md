---
status: pending
priority: p3
issue_id: "683"
tags: [forum, forum-categories, wagtail, admin, owner-check]
dependencies: ["668"]
triage: blocked-owner
triaged: 2026-11-22
blocked_on: "The owner opens /cms/forum/forums/ as staff, does the drag/reload/keyboard check and records the date."
owner_decision: "Owner delegated the live check to a Claude session driving Chrome (2026-11-22); run by hand outside the sweep"
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

### 2026-11-22 - Partial check run by Claude in desktop Chrome (owner-delegated 2026-11-22)

- **Keyboard alternative: PASS.** On live `/cms/forum/forums/`, focused "Move Garden design
  up" and pressed Enter. After a reload the order was Plant identification | Care & problems |
  Garden design | Pests & diseases. "Move Garden design down" then put the original order back,
  and it stayed after another reload.
- **Drag: NOT RUN.** Two synthetic drags of the handle did nothing: the browser tool's drag
  doesn't fire native HTML5 drag events, so this says nothing about the feature. The owner
  still has to drag, reload and check the order holds by hand.
- **Finding (visual, P3):** the up/down Move buttons render as wide, empty boxes. The
  `icon-arrow-up` / `icon-arrow-down` SVGs have no size (computed 300×150 px) inside a
  24 px-tall button, so no arrow shows. The screen-reader label is still there.
  `forum-structure.css` sizes only `.wf-structure__handle .icon`. Fix: give
  `.wf-structure__move .icon` a 1rem width and height.
