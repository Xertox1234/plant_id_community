# Forum Mobile-First Modernization Roadmap

**Version**: 1.0  
**Last Updated**: May 23, 2026  
**Scope**: Web forum frontend (React + Tailwind) — mobile browser + Flutter UI translation readiness  
**Owner**: Frontend/Forum team  
**Corrected**: Jul 16, 2026 — recovered from a `.gitignore` bug that kept this doc untracked for months (root cause in `docs/LEARNINGS.md`). That pass fixed stale paths/line numbers and marked Phase 5.1/5.2 shipped, but left Phases 1–4 unvalidated.

**Fully re-audited**: Jul 29, 2026 (todo 270). Every Phase 1–4 "Problem" statement was checked against the code on `main` and is now marked ✅ shipped / 🟡 partially shipped / ⬜ still open, and every file-path and line citation was re-resolved. Two false premises were corrected in place (Phase 2.2 `fetchThreads` pagination, Phase 4.4 image renditions) — both would have misdirected an implementer.

> **Citations**: line numbers are accurate as of Jul 29, 2026 but rot fast (this doc has rotted them twice). Each cite now names a nearby anchor — a function or JSX comment — so a drifted line number can be re-found by searching for the anchor.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State](#current-state)
3. [Target State](#target-state)
4. [Phase 1: Critical Touch Fixes](#phase-1-critical-touch-fixes)
5. [Phase 2: Responsive Layout Overhaul](#phase-2-responsive-layout-overhaul)
6. [Phase 3: Mobile-Native Interactions](#phase-3-mobile-native-interactions)
7. [Phase 4: Performance & Offline](#phase-4-performance--offline)
8. [Phase 5: Content Richness](#phase-5-content-richness)
9. [Testing Strategy](#testing-strategy)
10. [Flutter Translation Notes](#flutter-translation-notes)
11. [Acceptance Criteria](#acceptance-criteria)

---

## Executive Summary

The existing web forum works on desktop but has multiple features that are broken or hostile on mobile browsers. This roadmap modernizes the forum UI/UX with a strict mobile-first approach while keeping every component simple enough to be replicated in the Flutter app later.

**Key principle**: Every React component must be implementable as a single Flutter `Widget` with no external DOM dependencies.

---

## Current State

Re-verified against `main` on Jul 29, 2026 (todo 270). Rows that changed since the May 23 original are marked **(changed)**.

| Feature | Desktop | Mobile Browser | Flutter Translatable |
|---------|---------|----------------|----------------------|
| Category list | Works | Functional, no bottom nav | Yes |
| Thread list | Works | **(changed)** Toolbar stacks (`flex-col sm:flex-row`); cursor "Load More" at 44px | Partial |
| Thread detail | Works | **(changed)** Actions fixed; reply form still at page bottom, no FAB | Partial |
| Post reactions | Interactive | **(changed)** Tappable toggle + `+🙂` picker when signed in; read-only when anon | Yes |
| Post edit/delete | Hover/focus-reveal | **(changed)** Always visible below `md`; 44px targets | Yes |
| Image upload | Toolbar button in `TipTapEditor` | Uploads via file picker; no camera-to-post flow | No |
| TipTap editor | 7-button toolbar | **(changed)** Wraps (`flex-wrap`), 44px targets, no overflow | Partial |
| Search | Dedicated page + header entry | **(changed)** Full-width input; not an overlay | Yes |
| Breadcrumbs | Full trail | Wraps badly, wastes space | No |
| Pull-to-refresh | Not implemented | Not implemented | N/A |
| Infinite scroll | Not implemented | **(changed)** Manual cursor "Load More", not auto-scroll | N/A |
| Quote/reply | Not implemented | Not implemented | N/A |

### Files to Know

- `@/web/src/pages/forum/CategoryListPage.tsx` — Forum homepage
- `@/web/src/pages/forum/ThreadListPage.tsx` — Thread list per category
- `@/web/src/pages/forum/ThreadDetailPage.tsx` — Thread + posts + reply
- `@/web/src/pages/forum/SearchPage.tsx` — Forum search
- `@/web/src/components/forum/PostCard.tsx` — Individual post display
- `@/web/src/components/forum/ThreadCard.tsx` — Thread preview card
- `@/web/src/components/forum/TipTapEditor.tsx` — Rich text composer
- `@/web/src/services/forumService.ts` — API service layer
- `@/web/src/types/forum.ts` — TypeScript interfaces
- `@/web/src/utils/forumDrafts.ts` — composer draft persistence (see 4.2)

Backend paths in this doc written as `wagtail_forum/…` are **package-relative**: the
package uses a src layout, so `wagtail_forum/api/serializers.py` lives on disk at
`backend/packages/wagtail_forum/wagtail_forum/api/serializers.py`.

---

## Target State

A forum that feels native on a phone: large tap targets, no hover dependencies, swipe/scroll gestures, action sheets, sticky composers, and content that reflows gracefully on any width. Every pattern chosen should map 1:1 to a Flutter equivalent.

---

## Phase 1: Critical Touch Fixes

**Goal**: Make the forum functional on touch devices. No new features — just fix what's broken.

**Priority**: P0 — blocks mobile usage entirely

### 1.1 PostCard: Replace Hover Actions with Overflow Menu — ✅ Shipped (solved differently)

~~**Problem**: `@/web/src/components/forum/PostCard.tsx` (lines 58-59 *as of May 2026*) uses `onMouseEnter`/`onMouseLeave` to show edit/delete buttons. On touch devices these never appear.~~

**Done**: the hover dependency is gone — `PostCard.tsx` has no `onMouseEnter`/`onMouseLeave` and no `showActions` state. The action row (anchor: the `{/* Actions … */}` comment, `PostCard.tsx:167-199`) is `md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100`: **always visible below `md`**, hover-*and*-keyboard-focus reveal at `md+` (the focus half is WCAG 2.4.7, audit H20). Every button carries `min-h-11` (44px). Edit/delete are gated on the backend `can_edit`/`can_delete` flags; Report is a separate always-rendered control gated on `can_report` (`PostCard.tsx:285`).

**Not done — and deliberately not needed**: the prescribed `⋯` overflow menu + dropdown was *not* the route taken. Do not implement it thinking it is outstanding; the underlying touch problem is fixed. See 3.3 for what a real action sheet would still add.

<details><summary>Original fix plan (kept for reference)</summary>

- Remove `onMouseEnter`/`onMouseLeave` and `showActions` state.
- Always render a "More" (`⋯`) icon button in the post header when `canEdit` is true.
- On tap, open a small dropdown with Edit, Delete, and (future) Report options.
- Touch target minimum: `44x44` px.

**Flutter equivalent**: `PopupMenuButton` wrapping an `IconButton`.

</details>

### 1.2 PostCard: Make Reactions Interactive — ✅ Shipped

~~**Problem**: `@/web/src/components/forum/PostCard.tsx` (lines 135-151 *as of May 2026*) renders reaction counts as read-only buttons.~~

**Done**: reaction chips are tappable when an `onReact` handler is supplied (`PostCard.tsx:224-281`), plus a `+🙂` picker that reveals the not-yet-used reaction types. Active reactions render filled (`bg-primary/10 … ring-1 ring-primary/40`) and carry `aria-pressed`; anonymous visitors get the same chips `disabled` with no `aria-pressed` (they are not toggles). Targets are `min-h-11`.

Two deviations from the original plan, both intentional:
- The service exposes a single **`toggleReaction`** (`@/web/src/services/forumService.ts:259`), not the planned `addReaction`/`removeReaction` pair.
- Feedback is **post-response, not optimistic** — `handleReact` (`@/web/src/pages/forum/ThreadDetailPage.tsx:298`) awaits the API, then writes the server's `reaction_counts` and `reacted` into state. There is a `transition-colors` but no scale-bounce. This trades instant feedback for never showing a count that the server disagrees with.

<details><summary>Original fix plan (kept for reference)</summary>

- Add `onClick` to each reaction chip that toggles the user's reaction.
- Call `addReaction` / `removeReaction` from `@/web/src/services/forumService.ts`.
- Provide immediate visual feedback (scale bounce, color change) while API resolves.
- Show user's active reactions in filled style, inactive in outlined style.

**Flutter equivalent**: `Wrap` of `ChoiceChip` or `FilterChip` with `onSelected`.

</details>

### 1.3 TipTapEditor: Collapsible Toolbar for Narrow Viewports — ✅ Shipped (solved differently)

~~**Problem**: `@/web/src/components/forum/TipTapEditor.tsx` (line 74 *as of May 2026*) renders 14+ buttons in a single row that overflows on mobile.~~

**Done**: the overflow was removed by **shrinking the toolbar, not by grouping it**. The toolbar (anchor: the `{/* Toolbar */}` comment, `@/web/src/components/forum/TipTapEditor.tsx:167`) is `flex gap-1 flex-wrap` and now renders 7 controls — Bold, Italic, Bullet, Numbered, Inline Code, Link, Image (plus a conditional Remove-Link). Strike, headings, blockquote and code-block were dropped on purpose: the server's nh3 allowlist would flatten them to plain text anyway (`TipTapEditor.tsx:184-187`). Every `ToolbarButton` is `min-h-11 min-w-11` = 44px (audit L10). Fewer buttons + `flex-wrap` = no horizontal scroll at 375px.

**Not done — and deliberately not needed**: the 3-dropdown grouping (Text Style / Structure / Lists) and the sticky bottom-sheet toolbar. Several of the buttons those dropdowns would have grouped no longer exist.

<details><summary>Original fix plan (kept for reference)</summary>

- Detect viewport width (`useMediaQuery` or Tailwind responsive classes).
- On screens `< 640px`:
  - Group formatting into 3 dropdowns: **Text Style** (Bold, Italic, Strike), **Structure** (H2, H3, Quote, Code), **Lists** (Bullet, Numbered).
  - Always-visible: Link, undo/redo (if available).
- Touch target: minimum `44x44` px per button.
- Toolbar becomes a sticky bottom sheet on very small screens (optional enhancement).

**Flutter equivalent**: `ToggleButtons` in a `SingleChildScrollView` or `BottomSheet`.

</details>

### 1.4 ThreadDetailPage: Responsive Header — 🟡 Partially shipped

**Problem** (revised Jul 29, 2026 — this supersedes the "check before starting" hedge): the thread header (anchor: the `{/* Thread Header */}` comment, `@/web/src/pages/forum/ThreadDetailPage.tsx:512-572`) is `flex items-start flex-wrap gap-4`, **not** the specified `flex-col sm:flex-row`. There is therefore no unconditional vertical stacking below `sm` — the icon, title column (`flex-1 min-w-0`) and badge column share one flex line and reflow only by wrapping.

**Done**:
- Title is `text-xl sm:text-3xl` (`ThreadDetailPage.tsx:522`) — the responsive-sizing bullet is complete.
- The metadata row is `flex flex-wrap items-center gap-2 sm:gap-4` — it wraps and tightens its gap on narrow screens.
- `flex-wrap` on the container plus `min-w-0` on the title column means the header does not force horizontal overflow.

**Still open**:
- Explicit mobile stacking (`flex-col sm:flex-row`) with a guaranteed icon+title / metadata / badges vertical order.
- Badges (📌 Pinned, 🔒 Locked, the Follow button, `ThreadDetailPage.tsx:547-570`) are not deterministically placed below the title on narrow screens — where they land depends on whether the badge column's intrinsic width leaves room on the line.

**Flutter equivalent**: `Column` on small width, `Row` on wide — controlled by `LayoutBuilder`.

### 1.5 Breadcrumb: Collapsible on Mobile — ⬜ Still open

**Problem** (citations re-resolved Jul 29, 2026): both breadcrumbs still render the full trail. `@/web/src/pages/forum/ThreadDetailPage.tsx:491-510` shows Forums › Category › *thread title*; `@/web/src/pages/forum/ThreadListPage.tsx:187-200` shows Forums › Category. Both are `<ol className="flex items-center gap-2">` with **no** `flex-wrap` and no mobile variant, so a long thread title consumes vertical space by wrapping inside its `<li>`. Nothing in the Fix below has been implemented.

**Fix**:
- On mobile (`< 640px`): show only parent link + current page label. Replace intermediate items with a single "Back to Forums" link.
- Or collapse to: `< Back | Current Page Title`.

**Flutter equivalent**: `AppBar` with `leading: BackButton()` and `title: Text(...)`.

---

## Phase 2: Responsive Layout Overhaul

**Goal**: Every forum page reflows gracefully from 320px to 1440px. No horizontal scroll. No clipped content.

**Priority**: P1

### 2.1 ThreadListPage: Stacked Toolbar — 🟡 Partially shipped

**Problem** (citations re-resolved Jul 29, 2026): the toolbar (anchor: the `{/* Toolbar */}` comment, `@/web/src/pages/forum/ThreadListPage.tsx:216-252`) already stacks, but two of the three bullets below are unimplemented.

**Done**:
- The container is `flex flex-col sm:flex-row gap-4 justify-between items-start sm:items-center` — search sits above a row of sort dropdown + New Thread button on mobile, exactly as specified.
- The sort `<select>` carries `min-h-11` (44px tap height), pinned by an E2E assertion (`@/web/e2e/forum-responsive.spec.ts:52-64`).

**Still open**:
- `max-w-md` is still applied unconditionally to the search form (`ThreadListPage.tsx:219`). It is inert below 448px but does constrain the input on mid-size phones and tablets in portrait.
- The sort dropdown is not a full-**width** tap target — only full-height.

### 2.2 ThreadListPage: Infinite Scroll — ⬜ Still open

**Problem** (revised Jul 29, 2026 — this supersedes the "re-check relevance" hedge): pagination has been modernized to cursor-based, but it is still **manual**. `handleLoadMore` (`@/web/src/pages/forum/ThreadListPage.tsx:133`) fires only from the "Load More" button (anchor: the `{/* Load More (cursor pagination) … */}` comment, `ThreadListPage.tsx:270-290`). There is no `IntersectionObserver` anywhere in `web/src/` outside the jsdom mock in `@/web/src/tests/setup.ts:42`. The Fix below is entirely unimplemented; only the "Previous / Page N / Next" premise is obsolete.

**Fix**:
- Replace with an IntersectionObserver-based infinite scroll.
- Append next page of threads as user scrolls near the bottom.
- Show a `LoadingSpinner` skeleton at the bottom during fetch.
- Retain a "Load More" fallback button if `prefers-reduced-motion` is set.

**API impact** (corrected Jul 29, 2026 — the original claim was false): `fetchThreads` does **not** take `page`/`limit`. Its real signature is `{ board, cursor, sort }` (`@/web/src/services/forumService.ts:116-141`); `page`, `category`, `search` and `ordering` survive on the options type only as legacy fields — the function destructures just `{ board, cursor, sort }` and never reads them. Cursor pagination also omits a total, so `meta.count` falls back to `0` and pages seed real totals from `board.topic_count` / `thread.post_count` (audit M30). An infinite scroll must therefore drive off `meta.next`, and cannot compute "page N of M". Still no backend changes needed.

**Flutter equivalent**: `ListView.builder` with `NotificationListener<ScrollNotification>` or `ScrollController`.

### 2.3 ThreadDetailPage: Infinite Scroll for Posts — ⬜ Still open

**Problem** (citations re-resolved Jul 29, 2026): posts still load through a manual "Load More Posts" button (anchor: the `{/* Load More Button (cursor pagination) */}` comment, `@/web/src/pages/forum/ThreadDetailPage.tsx:629-649`), backed by `handleLoadMore` at `ThreadDetailPage.tsx:191`.

Note one piece of automatic paging that already exists and should be preserved by any infinite-scroll work: the **deep-link chase** (`ThreadDetailPage.tsx:230-255`) auto-calls `handleLoadMore` to pull cursor pages until a `#post-N` anchor target appears, guarded by `chaseCursorRef` so a failed load stops the chase instead of retrying forever. It is anchor-driven, not scroll-driven.

**Fix**:
- Same IntersectionObserver pattern as thread list.
- Reverse order if desired (newest first) or keep chronological (oldest first).
- Maintain scroll position when appending.

### 2.4 ThreadDetailPage: Floating Action Button (FAB) for Reply — ⬜ Still open

**Problem**: Reply form is at the bottom of all posts (anchor: the `{/* Reply composer … */}` comment, `@/web/src/pages/forum/ThreadDetailPage.tsx:651-693`). On long threads users must scroll extensively. No FAB and no bottom-sheet composer exist.

**Fix**:
- Add a sticky FAB in the bottom-right corner (bottom-center on mobile for thumb reach).
- Tapping FAB scrolls to the reply form and focuses the editor.
- On mobile, the reply form becomes a bottom-sheet modal that slides up over the post list.
- On desktop, inline form remains.

**Flutter equivalent**: `FloatingActionButton` + `showModalBottomSheet`.

### 2.5 SearchPage: Full-Screen Modal on Mobile — ⬜ Still open

**Problem** (re-verified Jul 29, 2026): `@/web/src/pages/forum/SearchPage.tsx` is still a dedicated page inside the normal layout. None of the four bullets below is implemented — the input has no `autoFocus` (`SearchPage.tsx:276-283`), there is no overlay/close affordance, and no recent-searches persistence.

Two things did land around it and are worth knowing before starting:
- The header links to `/forum/search` from both the desktop and mobile nav (`@/web/src/components/layout/Header.tsx:99` and `:201`), so the entry point already exists — this sub-phase is about the *presentation*, not discoverability.
- The board-level search box redirects here pre-filtered by board rather than searching in place (`handleSearch`, `@/web/src/pages/forum/ThreadListPage.tsx:107-117`), so `/forum/search` is the single real search surface and any overlay must keep honoring `?q=` and `?category=`.

**Fix**:
- Keep `/forum/search` route.
- On mobile: render search as a full-screen overlay with a top search bar, results below, and a close/done button.
- Autofocus the search input when entering.
- Show recent searches below the input (persisted in `localStorage`).

---

## Phase 3: Mobile-Native Interactions

**Goal**: Add interaction patterns that mobile users expect. These also map cleanly to Flutter.

**Priority**: P2

> **Phase 3 audit note (Jul 29, 2026)**: this phase had received *zero* verification before todo 270 — every claim below was as written on May 23. All five sub-phases were checked against `main`; 3.3 turned out partially shipped, the other four are confirmed still open.

### 3.1 Pull-to-Refresh — ⬜ Still open

**Problem** (re-verified Jul 29, 2026): confirmed unimplemented — `web/src/` contains no `touchstart`/`touchmove` handler, no pull-to-refresh library, and no refresh gesture on either list. No way to refresh content without browser chrome pull-down.

**Fix**:
- Add a pull-to-refresh gesture on thread list and thread detail (posts list).
- Use a touchstart/touchmove/scroll-top threshold or a library like `react-pull-to-refresh`.
- Show a refresh spinner and re-fetch data.
- **Backend impact**: None — uses existing `fetchThreads` / `fetchPosts`.

**Flutter equivalent**: `RefreshIndicator`.

### 3.2 Post Quote / Reply-to-Post — ⬜ Still open

**Problem** (re-verified Jul 29, 2026): confirmed unimplemented on both sides — no `quoted_post`/`parent_post` field anywhere in `wagtail_forum`, and no quote affordance in `PostCard`. `PostCard`'s only per-post link action is copy-link (`handleCopyLink`, `@/web/src/components/forum/PostCard.tsx:65`), which yields a `#post-N` deep link. No way to reference a specific post when replying.

**Fix**:
- Add a "Reply" button to each `PostCard` (visible on all posts, not just author's).
- Tapping "Reply" opens the composer pre-filled with a blockquote of the selected post's content (truncated to 200 chars + `...`).
- Quote attribution includes author name and post timestamp.
- Backend: add `parent_post_id` or `quoted_post_id` to `CreatePostInput`.
- **Backend impact**: Light — extend `PostSerializer` and `CreatePostSerializer` with an optional `quoted_post` field. No DB migration needed if stored as JSON or a simple nullable FK.

**Flutter equivalent**: `ListTile` with trailing `IconButton(Icons.reply)`.

### 3.3 Post Action Sheet — 🟡 Partially shipped

**Problem** (revised Jul 29, 2026): the *actions* now exist on mobile; the *action-sheet packaging* does not.

**Done** — every action is present as an always-tappable inline control, not behind a `⋯`:
- **Copy post link** — `handleCopyLink` (`@/web/src/components/forum/PostCard.tsx:65-76`) writes `…#post-{id}` to the clipboard, with a confirming "Copied ✓" and, when the Clipboard API is unavailable (http / old browser), a selectable read-only input as fallback rather than a `window.prompt` (audit M24, `PostCard.tsx:202-217`).
- **Report post** — reason `<select>` (spam / abuse / off-topic / other, mirroring `Report.REASON_CHOICES`) plus submit/cancel (`PostCard.tsx:283-334`), shown only when the backend's `can_report` is true, so never to the post's own author. It confirms "Reported" only after the request actually succeeds.
- **Edit / Delete** — gated on backend `can_edit` / `can_delete`; see 1.1.

**Still open**:
- **Share via Web Share API** — not implemented. `navigator.share` appears only as a jsdom mock in `@/web/src/tests/setup.ts:70-73`; no `web/src/` component calls it.
- **The sheet itself** — no `⋯` trigger, no slide-up bottom sheet on mobile, no dropdown on desktop. The controls sit inline in the post header and footer.

<details><summary>Original fix plan (kept for reference)</summary>

- "More" (`⋯`) button on every post opens a bottom sheet / dropdown:
  - Share link to post (uses Web Share API if available, fallback to clipboard)
  - Copy post link
  - Report post (if not author)
  - Edit / Delete (if author/moderator)
- On desktop: dropdown. On mobile: slide-up bottom sheet.

**Flutter equivalent**: `showModalBottomSheet` with a `Column` of `ListTile` options.

</details>

### 3.4 Sticky Composer on Mobile — ⬜ Still open

**Problem** (re-verified Jul 29, 2026): confirmed unimplemented — no `visualViewport` usage anywhere in `web/src/`, and the reply composer is a static form at the end of the page (`@/web/src/pages/forum/ThreadDetailPage.tsx:666-692`). Typing a long reply on mobile causes the virtual keyboard to obscure the submit button.

**Fix**:
- When the reply form is focused, make it a fixed bottom panel that sits above the keyboard.
- Use `visualViewport` API to track keyboard height and adjust the panel position.
- Show a "Cancel" and "Post" button always visible.
- Auto-resize textarea as content grows.

**Flutter equivalent**: `TextField` with `maxLines: null` inside a bottom sheet.

### 3.5 Image Gallery / Lightbox — ⬜ Still open

**Problem** (re-verified Jul 29, 2026): confirmed — no lightbox, gallery, or pinch-zoom code exists in `web/src/`. Image upload is handled inline in `TipTapEditor.tsx` (`handleImageSelect` → `uploadPostImage`, `@/web/src/components/forum/TipTapEditor.tsx:96-128`) rather than a dedicated widget — this doc's original `ImageUploadWidget.tsx` reference doesn't exist. Post images render as a single plain `<img>` per block (`@/web/src/components/StreamFieldRenderer.tsx:131`) — no grid, no viewer.

**Fix**:
- In `PostCard`: render post images in a responsive grid (1 col mobile, 2 col tablet, 3 col desktop).
- Tapping an image opens a full-screen lightbox with:
  - Swipe left/right to navigate multiple images
  - Pinch-to-zoom (or tap to toggle zoom)
  - Close button (X) or tap background to dismiss
- Use `react-use-gesture` or native touch events.

**Flutter equivalent**: `PageView` inside a `Dialog` with `PhotoView`.

---

## Phase 4: Performance & Offline

**Goal**: Forum feels instant even on slow networks. Content survives brief connectivity loss.

**Priority**: P2

> **Phase 4 audit note (Jul 29, 2026)**: like Phase 3, this phase had received *zero* verification before todo 270. 4.2 turned out already shipped; 4.4's stated backend premise turned out **false** and has been corrected below.

### 4.1 Skeleton Loading States — ⬜ Still open

**Problem** (re-verified Jul 29, 2026): every forum list still renders the generic `LoadingSpinner` — `@/web/src/pages/forum/ThreadListPage.tsx:256`, `@/web/src/pages/forum/ThreadDetailPage.tsx:462`, `@/web/src/pages/forum/SearchPage.tsx:342`. No `ThreadCardSkeleton` or `PostCardSkeleton` component exists. The only `animate-pulse` placeholder in the whole app is one block in `@/web/src/pages/forum/UserProfilePage.tsx:60` — a precedent to copy, not coverage. Mobile users need content placeholders.

**Fix**:
- Replace `LoadingSpinner` in forum pages with skeleton cards:
  - `ThreadCardSkeleton` — gray blocks mimicking title, excerpt, metadata
  - `PostCardSkeleton` — gray avatar circle, lines for content
- Use Tailwind `animate-pulse` on skeleton elements.

**Flutter equivalent**: `Shimmer` package or `Container` with `LinearGradient` animation.

### 4.2 Draft Persistence — ✅ Shipped

~~**Problem**: If a user navigates away while composing a reply, content is lost.~~

**Done**: `@/web/src/utils/forumDrafts.ts` provides `draftKey` / `loadDraft` / `saveDraft` / `clearDraft`, wired into both composers:
- **Reply drafts** — saved on every editor change and restored on thread entry (`@/web/src/pages/forum/ThreadDetailPage.tsx:131` restores, `:675-680` saves, `:267` clears on a successful post). The composer is remounted via `composerKey` so TipTap's init-only `content` actually picks the draft up.
- **New-thread drafts** — title + body persisted together as JSON, keyed per category (`@/web/src/pages/forum/NewThreadPage.tsx:39-49`, `:98-101`).

Four deviations from the original plan, all deliberate:
- **`sessionStorage`, not `localStorage`** — drafts survive navigation *and page reload within the tab*, but intentionally not across sessions.
- **Key is `forum-draft:{kind}:{id}`**, not `forum_draft_{threadId}` — `kind` distinguishes `reply` from `new-thread`.
- **Saves on every change**, not on a 3-second timer.
- **Restores silently**, with no "Restore draft?" prompt.

Every storage call is wrapped in try/catch and swallows failures: a draft is a convenience, never a correctness dependency (private mode / quota).

<details><summary>Original fix plan (kept for reference)</summary>

- Auto-save reply content to `localStorage` every 3 seconds while typing.
- Key: `forum_draft_{threadId}`.
- Restore draft when returning to the thread.
- Clear draft on successful post.
- Show "Restore draft?" prompt if draft exists.

**Flutter equivalent**: `SharedPreferences` or `hive`.

</details>

### 4.3 Offline Post Queue — ⬜ Still open

**Problem** (re-verified Jul 29, 2026): confirmed unimplemented — no IndexedDB, no queue, and no `online` event listener in `web/src/`. A failed `createPost` surfaces the error in the thread's notice banner and the composer keeps its text (4.2's draft is still in `sessionStorage`), but nothing retries. If connectivity drops while submitting a reply, the post is lost with an error.

**Fix**:
- On `createPost` failure (network error), store the pending post in an IndexedDB queue.
- Show a "Pending — will retry" banner with the post content grayed out.
- Retry queue when `online` event fires.
- Allow user to manually cancel/retry pending posts.

**Flutter equivalent**: `WorkManager` or custom queue with `sqflite`.

### 4.4 Image Optimization — ⬜ Still open (premise corrected)

**Problem** (re-verified Jul 29, 2026): post images render as a bare `<img src … class="rounded-lg max-w-full h-auto my-4 mx-auto">` (`@/web/src/components/StreamFieldRenderer.tsx:131`) with **no** `loading`, `decoding`, or `srcset` attribute. They are not served at *full* resolution, though — see the corrected premise below.

> **⚠️ Premise correction (Jul 29, 2026).** The original bullet "Backend already generates `thumbnail`, `large_thumbnail`, and original" is **false**, and the fix plan built on it is unbuildable as written. `serialize_image_for_api` (`backend/packages/wagtail_forum/wagtail_forum/api/serializers.py:254-271`) returns exactly one rendition per image — a bounded `max-1200x1200` — as `{id, url, alt, width, height}`. There is no `thumbnail`, no `large_thumbnail`, and the original is deliberately not exposed. So a single ~1200px asset is already the ceiling (not the 5000px-capped original), but it is also the *only* size available.

**Fix** (rewritten against the real API):
- **Backend first**: to do any real responsive selection, `serialize_image_for_api` must emit additional renditions (e.g. `width-400`, `width-800`) alongside the existing `max-1200x1200`. Keep the batched-rendition prefetch in `build_forum_image_map` (`serializers.py:274`) intact — it is what keeps the post-list query count flat, and naively adding renditions per image will reintroduce an N+1.
- Add `loading="lazy"` and `decoding="async"` to the forum `<img>` in `StreamFieldRenderer` — this half needs **no** backend change and is worth doing on its own.
- Once multiple renditions exist, use `srcset`/`sizes` for responsive selection; only then does the "small for grid, large for lightbox" split (3.5) become possible.

**Flutter equivalent**: `CachedNetworkImage` with different `memCacheWidth` per display size.

---

## Phase 5: Content Richness

**Goal**: Make the forum engaging and modern. These are feature additions, not fixes.

**Priority**: P3

### 5.1 @Mentions — ✅ Shipped (todo 253 slice 4)

~~**Problem**: No way to notify a specific user in a post.~~ Done: mention parsing and recipient resolution (`resolve_mentioned_users`, `wagtail_forum/mentions.py:64`), the `Notification` model (`wagtail_forum/models/notifications.py`), the notification fan-out (`create_notifications(…, verb=NotificationVerb.MENTION)`, `wagtail_forum/notifications.py:17`, called from `@/backend/apps/forum_host/notifications.py:193` and `:82`), and composer autocomplete (`ForumMention` TipTap node in `TipTapEditor.tsx`) are all live.

> **Citation corrected Jul 29, 2026 (todo 270)**: PR #467's version of this line credited
> `send_forum_mention_notification` at `@/backend/apps/core/services/notification_service.py:411`.
> That line does resolve — it is the method *definition* — but the method has **zero call sites**
> repo-wide and is not part of the shipped mention path. It is dead code, not the delivery
> mechanism. The real path is the `forum_host` fan-out cited above. This is the failure mode a
> resolves-to-a-real-line check cannot catch: the citation was valid, the claim around it was not.

<details><summary>Original fix plan (kept for reference)</summary>

- In `TipTapEditor`: detect `@` + typing, show a user autocomplete dropdown.
- Backend: parse `content_raw` for `@username` patterns on post creation.
- Call `send_forum_mention_notification` from `@/backend/apps/core/services/notification_service.py`.
- Render `@username` as a styled link to the user's profile.

**Backend impact**: Add mention parsing in `CreatePostSerializer.create`. Add `Notification` model for in-app persistence.

</details>

### 5.2 Topic Following / Watch Thread — ✅ Shipped (todo 253 slice 3)

~~**Problem**: No way to track a thread without posting in it.~~ Done: `TopicSubscription` model (`wagtail_forum/models/subscriptions.py`), subscribe/unsubscribe API (`wagtail_forum/api/subscriptions.py`), wired at `topics/<id>/subscription/` (`backend/apps/forum_host/api_urls.py`).

<details><summary>Original fix plan (kept for reference)</summary>

- Add a "Watch" / "Unwatch" toggle in the thread header.
- Backend: create `TopicSubscription` model (user FK + topic FK + created_at).
- Endpoints: `POST /api/v1/forum/topics/{id}/watch/`, `DELETE .../unwatch/`.
- Notifications: email or in-app when new posts arrive.

</details>

### 5.3 Post Voting (Upvote / Downvote) — ⬜ Still open

**Problem** (re-verified Jul 29, 2026): confirmed — `wagtail_forum` has no `PostVote` model and no `upvote`/`downvote` reaction choice. Reactions (`like`, `love`, `helpful`, `thanks`) are social. There's no quality signal.

**Fix**:
- Add `upvote`/`downvote` to `PostReaction` choices or a separate `PostVote` model.
- Display net score prominently on each post.
- Sort replies by score (optional per-thread setting).

### 5.4 Best Answer / Solved Marking — ⬜ Still open

**Problem** (re-verified Jul 29, 2026): confirmed — no `accepted_answer` field and no `is_solved` flag anywhere in `wagtail_forum`. Plant problem threads have no way to mark a solution. (This is also tracked as Wave 2 slice 2 / finding H6 under epic todo 273; treat that as the implementation home and this as the design sketch.)

**Fix**:
- Thread author or moderator can mark any post as "Accepted Answer".
- Visually highlight the accepted post (green border, checkmark badge).
- Sort accepted answer to top of replies.
- Backend: add `accepted_answer` nullable FK on `Topic`.

---

## Testing Strategy

### Manual Testing Matrix

| Test | iPhone SE | iPhone 14 | iPad Mini | Android Pixel |
|------|-----------|-----------|-----------|---------------|
| Tap edit/delete on own post | Required | Required | Required | Required |
| Tap reaction, see toggle | Required | Required | Required | Required |
| Scroll thread list, infinite load | Required | Required | Required | Required |
| Type reply with virtual keyboard | Required | Required | Required | Required |
| Tap FAB, open reply sheet | Required | Required | N/A | Required |
| Pull-to-refresh | Required | Required | Required | Required |
| Image lightbox swipe/zoom | Required | Required | Required | Required |
| Search modal overlay | Required | Required | Required | Required |

### Automated Testing

Re-verified Jul 29, 2026:

- **Playwright E2E**: `@/web/e2e/forum-authenticated.spec.js` exists. ✅ **Mobile viewport tests now exist too** — `@/web/e2e/forum-responsive.spec.ts` sweeps 375×812 / 768×1024 / 1280×800 (`:6-10`), asserting no horizontal overflow on the forum index, category list and thread detail, plus a 44px tap-target check on the sort select (`:52-64`). A third spec, `@/web/e2e/forum-golden-path.spec.ts`, covers the happy path. Gap: **320px is not covered** — the narrowest viewport tested is 375px, so the 320px acceptance criterion below is unproven.
- **Component tests**: all `*.test.tsx` files in `@/web/src/components/forum/` and `@/web/src/pages/forum/` must pass. These are the CI-gated ones (`.github/workflows/web-ci.yml` runs `npm run test -- --run`).
- **Accessibility**: Run Lighthouse CI on forum pages. Target 95+ mobile score. Not currently wired.

> **E2E caveats** — two, both worth knowing before trusting a green run:
>
> 1. Playwright is excluded from CI (see `@/web/CLAUDE.md`) and runs locally only, so "the spec exists" is *not* "the spec passes". This audit verified existence and content, not green runs.
> 2. **`forum-responsive.spec.ts` only ever runs signed-out.** The authenticated Playwright projects restrict themselves to `.js` specs (`testMatch: /(forum-authenticated|auth)\.spec\.js/`, `@/web/playwright.config.ts:134`), so the `.ts` responsive spec runs under the five anonymous projects. Anything gated behind auth — the reply composer and its TipTap toolbar, reaction toggling, edit/delete — is therefore **not** covered by the responsive assertions. Any new mobile spec that needs a signed-in view must either be `.js` or the project `testMatch` must be widened.

---

## Flutter Translation Notes

Every phase in this roadmap was chosen because the UI patterns have direct Flutter equivalents:

| Web Pattern | Flutter Widget |
|-------------|---------------|
| Overflow menu (`⋯`) | `PopupMenuButton` |
| Choice chips (reactions) | `ChoiceChip` / `FilterChip` |
| Bottom sheet composer | `showModalBottomSheet` |
| FAB for reply | `FloatingActionButton` |
| Infinite scroll list | `ListView.builder` + `ScrollController` |
| Pull-to-refresh | `RefreshIndicator` |
| Skeleton loader | `Shimmer` or animated `Container` |
| Image lightbox | `PageView` + `PhotoView` |
| Sticky bottom panel | `BottomSheet` or `Scaffold.bottomSheet` |
| Action sheet | `showModalBottomSheet` with `ListTile` |
| Search overlay | `showSearch` + `SearchDelegate` |

**State management parity**:
- React `useState` / `useReducer` → Flutter `ValueNotifier` / `ChangeNotifier`
- React Context auth → Flutter `Riverpod`/`Provider` auth service
- Service layer (`forumService.ts`) → Flutter `ForumService` class with `Dio`/`http`

---

## Acceptance Criteria

Checkbox states re-verified Jul 29, 2026 (todo 270); each checked box names its evidence.

### Phase 1 Complete When
- [x] Edit/delete actions visible and functional on touch devices — always rendered below `md`; hover/focus reveal at `md+` (1.1)
- [x] Reactions toggle on tap with visual feedback — `onReact` + `aria-pressed` + filled active style; feedback is post-response, not optimistic (1.2)
- [x] TipTap toolbar usable at 375px width without horizontal scroll — 7 buttons, `flex-wrap`, 44px targets (1.3). Evidence is the markup, **not** E2E: `forum-responsive.spec.ts` runs only under the unauthenticated Playwright projects (the `*-authenticated` projects `testMatch` `.js` specs only, `@/web/playwright.config.ts:134`), and an anonymous visitor gets the "Log in to post a reply" box instead of the composer (`@/web/src/pages/forum/ThreadDetailPage.tsx:656`), so the toolbar is never in the DOM during that spec
- [ ] Thread header and breadcrumb do not wrap awkwardly on mobile — header is 🟡 (1.4, no `flex-col sm:flex-row`); breadcrumb is ⬜ (1.5)

### Phase 2 Complete When
- [ ] Thread list uses infinite scroll; no pagination buttons on mobile — still a manual cursor "Load More" (2.2)
- [ ] Post list uses infinite scroll — still a manual "Load More Posts" (2.3)
- [ ] Reply accessible via FAB within 2 taps from any scroll position — no FAB (2.4)
- [ ] Search renders as full-screen overlay on mobile — still a plain page (2.5)
- [ ] No horizontal overflow on any forum page at 320px width — **unproven, not failed**: E2E asserts no overflow at 375/768/1280 only; 320px is untested

### Phase 3 Complete When
- [ ] Pull-to-refresh works on thread list and post list (3.1)
- [ ] Quote/reply-to-post pre-fills composer with attribution (3.2)
- [ ] Post action sheet offers share, copy-link, report, edit, delete — copy-link, report, edit and delete all ship as inline controls; **share and the sheet itself are missing** (3.3)
- [ ] Composer stays above virtual keyboard on mobile (3.4)
- [ ] Image lightbox supports swipe and tap-to-close (3.5)

### Phase 4 Complete When
- [ ] Skeleton loaders replace spinners on all forum lists — forum lists still use `LoadingSpinner` (4.1)
- [x] Draft persists across navigation and page reloads — `forumDrafts.ts` in both composers; `sessionStorage`, so it survives reload but is cleared when the tab closes (4.2)
- [ ] Offline post queue retries automatically on reconnection (4.3)
- [ ] Images use lazy loading and responsive srcset — neither attribute is set, and only one rendition exists to select from (4.4)

### Phase 5 Complete When
- [x] @mentions autocomplete in composer
- [x] Watch/unwatch threads with notification support
- [ ] Post upvote/downvote with score display
- [ ] Accepted answer marking and visual prominence

---

## Dependencies & Risks

| Risk | Mitigation |
|------|------------|
| TipTap mobile toolbar may require new extensions | Evaluate `@tiptap/extension-bubble-menu` or custom floating menu |
| Infinite scroll can cause memory bloat | Implement virtualized list with `react-window` or manual DOM recycling |
| Bottom-sheet keyboard handling is brittle | Use `visualViewport` API; test on iOS Safari and Android Chrome |
| Backend lacks `PostVote` model and any `accepted_answer` field (`TopicSubscription` now exists — 5.2 shipped) | Backend team to deliver the Phase 5.3/5.4 APIs before frontend starts those sub-phases |
| Only one image rendition (`max-1200x1200`) is exposed by the API — 4.4's responsive-image work is backend-blocked | Add renditions in `serialize_image_for_api` *without* breaking `build_forum_image_map`'s batched prefetch (N+1 risk) |
| E2E specs exist but their pass/fail status is unverified — Playwright is excluded from CI and runs locally only | Run `npm run test:e2e` locally before relying on them. (The `todos/092-...` ticket this doc originally cited is unrelated — that number belongs to an already-completed backend ticket, not an E2E one.) |
