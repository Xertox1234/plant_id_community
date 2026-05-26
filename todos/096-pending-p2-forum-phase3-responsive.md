---
status: pending
priority: p2
issue_id: "096"
tags: [forum, web, frontend, responsive]
dependencies: ["094", "095"]
---

# Forum Phase 3 — make the forum usable on mobile browsers

## Problem

The forum needs to adapt cleanly to phone/tablet browsers. The components are
already mostly mobile-first, but a few real touch/mobile gaps remain and there are
no viewport regression tests.

## Findings

From a layout audit of the forum pages/components:

- **Already responsive:** responsive container padding, `flex-col sm:flex-row`
  toolbars, responsive grids (SearchPage, ImageUploadWidget), `flex-wrap` metadata,
  no fixed pixel widths, no obvious page-level horizontal scroll.
- **Real gaps:** `PostCard` edit/delete are **hover-only** (no touch affordance);
  small controls (reactions, pagination, image reorder `←`/`→`) may be **< 44px**
  tap targets; sanitized `prose` content (code blocks, wide images, tables, long
  URLs) can **overflow** at 375px; `PostCard` header lacks `flex-wrap`.

## Recommended Action

Execute the Phase 3 plan task-by-task in a fresh session:
**`docs/superpowers/plans/2026-05-25-forum-phase3-responsive.md`**

It is scoped honestly as **audit + targeted polish** (not a rebuild): fix hover-only
actions for touch, enforce 44px tap targets, contain rich-content overflow, polish
header wrapping, and add Playwright viewport tests at 375/768/1280.

## Technical Details

- Plan: `docs/superpowers/plans/2026-05-25-forum-phase3-responsive.md`
- Spec: `docs/superpowers/specs/2026-05-25-forum-modernization-hardening-design.md`
- Patterns: `web/RESPONSIVE_LAYOUT_PATTERNS.md`, `web/docs/patterns/tailwind.md`
  (Mobile-First, Minimum Tap Targets, Dark Mode).

## Acceptance Criteria

- [ ] No page-level horizontal scroll at 375 / 768 / 1280 (viewport e2e green).
- [ ] All forum controls touch-reachable and ≥ 44px.
- [ ] Rich post content (code, images, tables, long URLs) stays within the viewport.
- [ ] Golden path manually verified at phone width, light + dark mode.
- [ ] `npm run type-check`, `npm run lint`, `npm run test` green in `web/`.

## Work Log

### 2026-05-25 - Created

- Spec + Phase 3 plan written and committed on `feat/forum-web-modernization`.
  Audit showed components are already mobile-first; plan scoped to targeted polish.
  Todo created.

## Notes

Depends on [todo 094] (working forum) and [todo 095] (so polish lands on the final,
secured UI). Priority p2 — UX polish after the forum works and is safe.
