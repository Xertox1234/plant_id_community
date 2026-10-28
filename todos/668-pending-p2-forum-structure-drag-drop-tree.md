---
status: pending
priority: p2
issue_id: "668"
tags: [forum, forum-categories, backend, wagtail, admin, web-js]
dependencies: ["666"]
---

# Forum categories slice 4: drag-and-drop forum structure tree in the Wagtail admin

## Problem

Staff need to arrange categories and forums. phpBB has only move-up/down arrows and Discourse removed drag and drop; a drag-and-drop tree is the owner's request and a differentiator.

## Findings

- Spec §5; phpBB/Discourse reorder UX in §2.
- Wagtail bundles SortableJS in `wagtailadmin/js/vendor.js`, but it is not a public API — pin our own copy.
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Make the structure tree the *Forum* menu's landing screen: categories in position order, each with its forums, row actions (edit, add forum, delete).
2. Drag operations: reorder categories; reorder forums within a category; move a forum to another category.
3. One POST endpoint `{forum_id, parent_id, position}`; validates type/parent rules and permissions; renumbers sibling positions in one transaction; an illegal drop returns 4xx and the UI snaps back with a message.
4. Keyboard-accessible alternative (move up/down/to-category buttons) for accessibility.

## Technical Details

- Pinned SortableJS (vendored static file, exact version), a Stimulus controller or small script, endpoint in `admin_urls.py`.
- Moving a forum to another category does not change topic URLs (ids only), so no redirects needed.
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [ ] Test: each of the three moves persists and positions stay contiguous (0..n-1) per parent.
- [ ] Test: dropping a category into a category, a forum at root, or anything under a link/forum is rejected.
- [ ] Test: endpoint requires the change permission and a CSRF token.
- [ ] Manual browser check recorded with date: drag, reload, order kept; keyboard alternative works.

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).
