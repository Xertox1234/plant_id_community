---
status: pending
priority: p2
issue_id: "666"
tags: [forum, forum-categories, backend, wagtail, admin]
dependencies: ["665"]
triage: ready
triaged: 2026-10-28
---

# Forum categories slice 2: Forum admin menu in Wagtail with create/edit forms

## Problem

After slice 1 forums are plain models, so staff need somewhere to create and edit categories, forums and link forums. The owner wants this inside the Wagtail admin but forum-specific, not the CMS page explorer.

## Findings

- Owner decision: admin inside Wagtail, not CMS pages — `docs/superpowers/specs/2026-10-28-forum-categories-design.md` §1, §5.
- Existing pattern for forum admin URLs + menu items: `backend/packages/wagtail_forum/wagtail_forum/wagtail_hooks.py:390-440` (`register_admin_urls`, `register_reports_menu_item`).
- phpBB ACP field grouping: spec §2.
- Source: owner request + phpBB/Discourse research, 2026-10-28 (Claude session).

## Recommended Action

1. Register a `ModelViewSet` (or `SnippetViewSet` if revisions are wanted — default: ModelViewSet, no revisions) for `Forum` under a top-level *Forum* menu.
2. Edit form tabs: General (type, category, name, slug, description) for now; later slices add Display, Rules, Pruning, Permissions tabs.
3. Type-aware form offering **category and forum only** (the `link` type and its URL field arrive in todo 670): category hides the parent field; forum requires a category; the type is read-only on edit (changing it is slice 667).
4. Permission: only users with the `Forum` add/change model permissions see the menu.
5. Delete stays disabled in this slice (slice 667 adds the safe flow).

## Technical Details

- `wagtail_hooks.py`, a new `wagtail_forum/admin/forums.py` (viewset), templates under `templates/wagtail_forum/admin/`.
- Wagtail 8.0 `ModelViewSet` docs (Context7 `/wagtail/wagtail`).
- Design: `docs/superpowers/specs/2026-10-28-forum-categories-design.md`. Web only — no Flutter changes.

## Acceptance Criteria

- [ ] Test: a staff user with the model permissions sees the *Forum* menu and can create a category and a forum in it; a user without them gets 403.
- [ ] Test: the form rejects a forum without a category and a category with a parent (server-side, not just hidden fields).
- [ ] Test: the delete URL is not exposed / returns 403 or 404 in this slice.
- [ ] Created forums appear on the web index without a deploy (manual check, dated, in the Work Log).

## Work Log

### 2026-10-28 - Filed

- Filed from the forum-categories research session (owner decisions in the design spec §1).

### 2026-10-28 - Advisor review of the spec

- Amended after an advisor review of the spec (slug constraint, page-row deletion order, link-type placement, Flutter list filter, naming).
