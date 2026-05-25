# Forum Phase 3 — "Make It Fit" (Responsive) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the forum comfortably usable on phone/tablet browsers — close the real mobile gaps (touch affordances, tap-target sizes, rich-content overflow) and lock the result in with viewport regression tests.

**Architecture:** The forum pages/components are **already mobile-first** (responsive padding, `flex-col sm:flex-row` toolbars, responsive grids in SearchPage/ImageUploadWidget, `flex-wrap` metadata, no fixed pixel widths, no horizontal scroll). So this phase is an **audit + targeted polish**, not a rebuild: fix hover-only actions for touch, enforce minimum tap targets, prevent rich-content (code/images/tables) overflow, and add Playwright viewport tests. Follow `web/RESPONSIVE_LAYOUT_PATTERNS.md` and `web/docs/patterns/tailwind.md`.

**Tech Stack:** React 19, Tailwind CSS 4 (mobile-first), Playwright (viewport e2e). Breakpoints: `sm 640 / md 768 / lg 1024 / xl 1280`.

**Spec:** `docs/superpowers/specs/2026-05-25-forum-modernization-hardening-design.md`
**Depends on:** Phase 1 (working forum) and Phase 2 (so you're polishing the final, secured UI).

---

## Verified state (current responsiveness — from a layout audit)

| Component | Current state |
|---|---|
| `CategoryListPage` | `max-w-7xl` container, responsive padding, vertical `space-y-4` list — **fine** |
| `ThreadListPage` | `flex-col sm:flex-row` toolbar, full-width search — **fine** |
| `ThreadDetailPage` | `max-w-5xl`, vertical flow, header `flex items-start gap-4` — **mostly fine** |
| `SearchPage` | filter grid `grid-cols-1 md:grid-cols-2 lg:grid-cols-4` — **fine** |
| `ThreadCard` | `flex-wrap` metadata, no fixed widths — **fine** |
| `PostCard` | **FIX** — hover-only edit/delete actions (no touch equivalent); header `flex justify-between` without `flex-wrap`; reaction buttons may be small |
| `TipTapEditor` | minor — toolbar `flex-wrap` (wraps, acceptable); `prose max-w-none` content |
| `ImageUploadWidget` | **tap targets** — preview grid `grid-cols-2 md:grid-cols-3`; reorder `←`/`→` small |

**The real mobile gaps (not a rebuild):**

1. **Touch affordances** — `PostCard` edit/delete reveal on hover; touch devices have no hover.
2. **Tap targets** — reaction buttons, pagination, reorder arrows, icon buttons may be `< 44px` (see `web/docs/patterns/tailwind.md` → Minimum Tap Targets).
3. **Rich-content overflow** — sanitized `prose` content (code blocks, wide images, tables, long URLs) can force horizontal scroll on a 375px screen.
4. **Header/metadata crowding** — `PostCard` header lacks `flex-wrap`.
5. **No viewport regression tests.**

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `web/src/components/forum/PostCard.tsx` | Modify | Touch-visible actions; `flex-wrap` header; tap-sized reaction buttons; `overflow-x-auto` on rich content |
| `web/src/components/forum/ImageUploadWidget.tsx` | Modify | Tap-sized reorder/delete controls |
| `web/src/pages/forum/ThreadListPage.tsx` | Modify | Tap-sized pagination/order controls (if under 44px) |
| `web/src/pages/forum/ThreadDetailPage.tsx` | Modify | Tap-sized "load more"/reply controls; header wrap |
| `web/src/pages/forum/SearchPage.tsx` | Modify | Tap-sized pagination (if needed) |
| `web/src/components/forum/TipTapEditor.tsx` | Modify | (Optional) denser toolbar on mobile |
| `web/e2e/forum-responsive.spec.ts` | Create | Playwright viewport tests (375 / 768 / 1280) |

Run web commands from `web/`. Each task ends with `npm run type-check` clean.

---

## Task 1: Responsive audit (produce the precise fix list)

- [ ] **Step 1: Audit at three widths in a real browser**

Start the stack (backend `:8000`, web `:5174`). In a browser with device emulation, load `/forum`, a category, a thread (with a long post incl. a code block + a wide image), and `/forum/search` at **375px, 768px, 1280px**. Use the checklist in `web/RESPONSIVE_LAYOUT_PATTERNS.md` → "Testing Checklist".

- [ ] **Step 2: Record findings**

For each width, note any: horizontal scroll, content clipped/overflowing, controls smaller than ~44px, hover-only affordances, text too small, overlapping elements. Append the list to this plan. Tasks 2–6 cover the expected fixes; **add tasks for anything else the audit surfaces.**

- [ ] **Step 3: Commit the findings**

```bash
git add docs/superpowers/plans/2026-05-25-forum-phase3-responsive.md
git commit -m "docs(forum): record Phase 3 responsive audit findings"
```

---

## Task 2: Touch affordances for post actions

`PostCard` edit/delete currently rely on hover. Make them reachable on touch (always visible on small screens, or behind an always-tappable overflow menu).

**Files:**

- Modify: `web/src/components/forum/PostCard.tsx`

- [ ] **Step 1: Make actions touch-reachable**

Replace hover-gated visibility (e.g. `opacity-0 group-hover:opacity-100`) with classes that are visible on touch widths and hover-revealed only from `md` up:

```tsx
// actions container: visible by default on mobile, hover-revealed on desktop
className="flex gap-1 opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity"
```

(If actions aren't currently in a `group`/hover wrapper, simply keep them always visible — the simplest correct behavior.)

- [ ] **Step 2: Add a component test**

```tsx
// PostCard.test.tsx — assert edit/delete controls are in the document for an
// owner without requiring hover (they should render, not be display:none).
```

- [ ] **Step 3: Run + commit**

Run: `cd web && npx vitest run src/components/forum/PostCard.test.tsx && npm run type-check`

```bash
git add web/src/components/forum/PostCard.tsx web/src/components/forum/PostCard.test.tsx
git commit -m "fix(forum): make post actions reachable on touch devices"
```

---

## Task 3: Minimum tap targets (44px)

Per `web/docs/patterns/tailwind.md` → Minimum Tap Targets, interactive controls should be ≥ 44px. Apply `min-h-11 min-w-11` (44px) + adequate padding to small icon/text buttons.

**Files:**

- Modify: `web/src/components/forum/PostCard.tsx` (reaction buttons)
- Modify: `web/src/components/forum/ImageUploadWidget.tsx` (reorder `←`/`→`, delete)
- Modify: `web/src/pages/forum/ThreadListPage.tsx`, `ThreadDetailPage.tsx`, `SearchPage.tsx` (pagination / "load more" / order select — only where under 44px)

- [ ] **Step 1: Reaction buttons (`PostCard`)**

```tsx
<button
  type="button"
  onClick={() => onReact?.(post.id, 'like')}
  className="inline-flex items-center justify-center gap-1 min-h-11 px-3 rounded-md hover:bg-gray-100"
  aria-label="React like"
>
  👍 <span>{post.reaction_counts?.like ?? 0}</span>
</button>
```

Apply the same sizing to `love`/`helpful`/`thanks`.

- [ ] **Step 2: Reorder/delete controls (`ImageUploadWidget`)**

Give the `←`/`→`/delete buttons `min-h-11 min-w-11 inline-flex items-center justify-center` (keep them visible, not hover-only — same touch concern as Task 2).

- [ ] **Step 3: Pagination / load-more / order controls**

Where pagination buttons or the order `<select>` are smaller than 44px tall, add `min-h-11` (and `px-4` for text buttons).

- [ ] **Step 4: Run + commit**

Run: `cd web && npm run type-check && npx vitest run src/components/forum`

```bash
git add web/src/components/forum web/src/pages/forum
git commit -m "fix(forum): enforce 44px minimum tap targets on forum controls"
```

---

## Task 4: Prevent rich-content overflow

Sanitized post content renders via `prose max-w-none` and can include code blocks, wide images, tables, and long unbroken URLs that force horizontal scroll at 375px.

**Files:**

- Modify: `web/src/components/forum/PostCard.tsx`

- [ ] **Step 1: Constrain the rendered content wrapper**

On the `dangerouslySetInnerHTML` content container, add wrapping + scoped horizontal scroll for wide children:

```tsx
className="prose prose-sm sm:prose max-w-none break-words
           prose-pre:overflow-x-auto prose-img:max-w-full prose-img:h-auto
           prose-table:block prose-table:overflow-x-auto"
```

`break-words` handles long URLs; `prose-pre:overflow-x-auto` keeps code blocks from blowing out the layout; `prose-img:max-w-full` makes images fluid; tables scroll within their own box.

- [ ] **Step 2: Verify with a seeded long post**

Manually confirm at 375px: a post with a long code block, a 2000px-wide image, and a long URL produces **no page-level horizontal scroll** (scrolling is confined to the code/table boxes).

- [ ] **Step 3: Commit**

```bash
git add web/src/components/forum/PostCard.tsx
git commit -m "fix(forum): keep rich post content within the viewport on mobile"
```

---

## Task 5: Header / metadata wrapping polish

**Files:**

- Modify: `web/src/components/forum/PostCard.tsx`
- Modify: `web/src/pages/forum/ThreadDetailPage.tsx`

- [ ] **Step 1: PostCard header**

Add `flex-wrap gap-2` to the `flex items-start justify-between` header row so author info and actions wrap instead of crowding at narrow widths.

- [ ] **Step 2: ThreadDetailPage header**

Ensure the `flex items-start gap-4` thread header wraps gracefully (`flex-wrap`) and the title (`text-2xl`+) uses responsive sizing (e.g. `text-xl sm:text-2xl`) per `RESPONSIVE_LAYOUT_PATTERNS.md` → Responsive Typography.

- [ ] **Step 3: Run + commit**

Run: `cd web && npm run type-check`

```bash
git add web/src/components/forum/PostCard.tsx web/src/pages/forum/ThreadDetailPage.tsx
git commit -m "fix(forum): wrap forum headers/metadata cleanly on narrow screens"
```

---

## Task 6: (Optional) denser TipTap toolbar on mobile

The toolbar already `flex-wrap`s (acceptable). Only if the audit (Task 1) flagged it as awkward: group secondary actions (H2/H3, code, quote) into an overflow row or a compact menu below `sm`. Skip if the wrapped toolbar reads fine.

**Files:**

- Modify: `web/src/components/forum/TipTapEditor.tsx`

- [ ] **Step 1: (Conditional) implement + commit**

```bash
git add web/src/components/forum/TipTapEditor.tsx
git commit -m "polish(forum): tidy TipTap toolbar on small screens"
```

---

## Task 7: Playwright viewport regression tests

**Files:**

- Create: `web/e2e/forum-responsive.spec.ts`

- [ ] **Step 1: Write the viewport spec**

```typescript
// web/e2e/forum-responsive.spec.ts
import { test, expect } from '@playwright/test';

const VIEWPORTS = [
  { name: 'mobile', width: 375, height: 812 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1280, height: 900 },
];

for (const vp of VIEWPORTS) {
  test(`forum has no horizontal overflow at ${vp.name} (${vp.width}px)`, async ({ page }) => {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto('/forum');
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    // No page-level horizontal scroll.
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1
    );
    expect(overflow, 'page should not scroll horizontally').toBe(false);

    // Drill into a category and a thread, re-checking overflow.
    await page.locator('a[href^="/forum/"]').first().click();
    await expect(page).toHaveURL(/\/forum\/\d+-/);
    const overflow2 = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1
    );
    expect(overflow2).toBe(false);
  });
}
```

- [ ] **Step 2: Run**

Run: `cd web && npm run test:e2e -- forum-responsive`
Expected: PASS at all three viewports. Fix any overflow the test catches (loop back to the relevant component task).

- [ ] **Step 3: Commit**

```bash
git add web/e2e/forum-responsive.spec.ts
git commit -m "test(forum): viewport regression tests (375/768/1280) for the forum"
```

---

## Task 8: Manual verification (real mobile-width browser)

- [ ] **Step 1: Walk the golden path on a phone-width browser**

At 375px, manually exercise: browse categories → open a category → open a thread → read a long post (code/image) → tap a reaction → (logged in) reply with the editor → upload an image. Confirm every control is tappable, nothing overflows, and text is readable. Check dark mode too (per `web/docs/patterns/tailwind.md` → Dark Mode).

- [ ] **Step 2: Note results in the PR description** (golden path verified at 375/768/1280; dark mode checked).

---

## Self-Review (completed during authoring)

- **Spec coverage:** mobile overhaul per the responsive/tailwind pattern docs (T2–T6), real mobile-width verification (T8), viewport tests (T7). Scope is honestly framed as audit + targeted polish because the components are already mobile-first — no speculative rebuild.
- **Audit-driven:** T1 produces the precise fix list; T2–T6 are the expected fixes; the plan instructs adding tasks for anything else T1 surfaces (not a placeholder — a defined discovery step with concrete follow-ups).
- **Tap targets / overflow / touch** are the three substantive, verifiable fixes; each has a test or a manual check.

## Definition of Done (Phase 3)

- No page-level horizontal scroll at 375 / 768 / 1280 (viewport e2e green).
- All forum controls are touch-reachable and ≥ 44px.
- Rich post content (code, images, tables, long URLs) stays within the viewport.
- Golden path manually verified at phone width, light + dark mode.
- `npm run type-check`, `npm run lint`, `npm run test` green.
