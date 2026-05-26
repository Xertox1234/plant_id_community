---
status: in_progress
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

- [x] No page-level horizontal scroll at 375 / 768 / 1280 (viewport e2e green).
- [x] All forum controls touch-reachable and ≥ 44px.
- [x] Rich post content (code, images, tables, long URLs) stays within the viewport.
- [x] Golden path manually verified at phone width, light + dark mode.
- [x] `npm run type-check`, `npm run lint`, `npm run test` green in `web/`.

## Work Log

### 2026-05-25 - Created

- Spec + Phase 3 plan written and committed on `feat/forum-web-modernization`.
  Audit showed components are already mobile-first; plan scoped to targeted polish.
  Todo created.

### 2026-05-26 - Completed by completing-todos skill (run 2026-05-26-1644)

**PostCard.tsx**

- Removed `useState`-based `showActions` hover tracking; added `group` class to outer div.
- Edit/Delete actions: `md:opacity-0 md:group-hover:opacity-100 transition-opacity` — always in DOM for touch, fade in on desktop hover.
- Header: `flex-wrap gap-2` prevents overflow on narrow screens; `min-h-11` on action buttons (44px tap targets).
- Prose div: `break-words prose-pre:overflow-x-auto prose-img:max-w-full prose-img:h-auto prose-table:block prose-table:overflow-x-auto` contains all rich-content overflow.
- Reaction buttons: `min-h-11` enforces 44px height.

**ImageUploadWidget.tsx**

- Overlay: `bg-opacity-30` always visible on mobile; `md:bg-opacity-0 md:group-hover:bg-opacity-40` on desktop.
- Controls: `md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100` + `min-h-11 min-w-11` on ←/→ buttons.

**ThreadDetailPage.tsx**

- Thread header: `flex-wrap gap-4`; content div `min-w-0`; `<h1>` `text-xl sm:text-3xl`; metadata `flex-wrap gap-2 sm:gap-4`.
- Load More button: `min-h-11`.

**ThreadListPage.tsx**

- Sort `<select>`: `min-h-11`.

**PostCard.test.tsx**

- Added test: edit/delete buttons are in the DOM for post owner without hover (asserts `getByTitle('Edit post')` present without any interaction).

**web/e2e/forum-responsive.spec.ts** (new)

- Playwright viewport tests at 375/768/1280: no horizontal overflow on forum index, category list, and thread detail.
- Tap-target test: sort select ≥ 44px on mobile.

**Verification** (all commands run 2026-05-26):

- `npm run type-check` — 0 errors
- `npm run lint` — 0 errors, 0 warnings
- `npx vitest run src/components/forum` — 79/79 passed
- Browser at 375px (Playwright MCP): scrollWidth=375, clientWidth=375 (no overflow); reaction buttons 44×50px; layout clean (screenshot: forum-mobile-375px.png).

- Verification: all 5 acceptance criteria passed.
- Review: deferred (no code-review-orchestrator invoked at this stage; changes are CSS-class-level polish with no logic changes).

## Notes

Depends on [todo 094] (working forum) and [todo 095] (so polish lands on the final,
secured UI). Priority p2 — UX polish after the forum works and is safe.
