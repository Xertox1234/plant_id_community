# Forum Mobile-First Modernization Roadmap

**Version**: 1.0  
**Last Updated**: May 23, 2026  
**Scope**: Web forum frontend (React + Tailwind) — mobile browser + Flutter UI translation readiness  
**Owner**: Frontend/Forum team  
**Corrected**: Jul 16, 2026 — recovered from a `.gitignore` bug that kept this doc untracked for months (root cause in `docs/LEARNINGS.md`). Applied in that pass:
- Stale file paths/line numbers fixed throughout.
- Phase 5.1 (@Mentions) and 5.2 (Topic Following) marked shipped.
- Everything else is unvalidated since May 23 — Phase 1.4/2.2 show signs of partial completion. Full re-audit tracked in todo 270.

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

| Feature | Desktop | Mobile Browser | Flutter Translatable |
|---------|---------|----------------|----------------------|
| Category list | Works | Functional, no bottom nav | Yes |
| Thread list | Works | Search bar crushes; pagination buttons tiny | Partial |
| Thread detail | Works | Reply form buried; hover actions broken | Partial |
| Post reactions | Display only | Display only; not tappable | Yes (read-only) |
| Post edit/delete | Hover-reveal | **Permanently invisible** | No |
| Image upload | Widget exists | No camera-to-post flow | No |
| TipTap editor | Full toolbar | Toolbar overflows viewport | Partial |
| Search | Works | Input + button compete for width | Yes |
| Breadcrumbs | Full trail | Wraps badly, wastes space | No |
| Pull-to-refresh | Not implemented | Not implemented | N/A |
| Infinite scroll | Not implemented | Not implemented | N/A |
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

---

## Target State

A forum that feels native on a phone: large tap targets, no hover dependencies, swipe/scroll gestures, action sheets, sticky composers, and content that reflows gracefully on any width. Every pattern chosen should map 1:1 to a Flutter equivalent.

---

## Phase 1: Critical Touch Fixes

**Goal**: Make the forum functional on touch devices. No new features — just fix what's broken.

**Priority**: P0 — blocks mobile usage entirely

### 1.1 PostCard: Replace Hover Actions with Overflow Menu

**Problem**: `@/web/src/components/forum/PostCard.tsx:58-59` uses `onMouseEnter`/`onMouseLeave` to show edit/delete buttons. On touch devices these never appear.

**Fix**:
- Remove `onMouseEnter`/`onMouseLeave` and `showActions` state.
- Always render a "More" (`⋯`) icon button in the post header when `canEdit` is true.
- On tap, open a small dropdown with Edit, Delete, and (future) Report options.
- Touch target minimum: `44x44` px.

**Flutter equivalent**: `PopupMenuButton` wrapping an `IconButton`.

### 1.2 PostCard: Make Reactions Interactive

**Problem**: `@/web/src/components/forum/PostCard.tsx:135-151` renders reaction counts as read-only buttons.

**Fix**:
- Add `onClick` to each reaction chip that toggles the user's reaction.
- Call `addReaction` / `removeReaction` from `@/web/src/services/forumService.ts`.
- Provide immediate visual feedback (scale bounce, color change) while API resolves.
- Show user's active reactions in filled style, inactive in outlined style.

**Flutter equivalent**: `Wrap` of `ChoiceChip` or `FilterChip` with `onSelected`.

### 1.3 TipTapEditor: Collapsible Toolbar for Narrow Viewports

**Problem**: `@/web/src/components/forum/TipTapEditor.tsx:74` renders 14+ buttons in a single row that overflows on mobile.

**Fix**:
- Detect viewport width (`useMediaQuery` or Tailwind responsive classes).
- On screens `< 640px`:
  - Group formatting into 3 dropdowns: **Text Style** (Bold, Italic, Strike), **Structure** (H2, H3, Quote, Code), **Lists** (Bullet, Numbered).
  - Always-visible: Link, undo/redo (if available).
- Touch target: minimum `44x44` px per button.
- Toolbar becomes a sticky bottom sheet on very small screens (optional enhancement).

**Flutter equivalent**: `ToggleButtons` in a `SingleChildScrollView` or `BottomSheet`.

### 1.4 ThreadDetailPage: Responsive Header

**Problem**: `@/web/src/pages/forum/ThreadDetailPage.tsx:372` (corrected — was cited as `components/forum/...:222-260`, which doesn't exist) uses `flex items-start gap-4` with `text-3xl` title and badges. Wraps poorly on mobile. Note: the title is already `text-xl sm:text-3xl`, so the responsive-sizing part of this fix may be done — check before starting.

**Fix**:
- Stack vertically on mobile: icon + title on top line, metadata second, badges third.
- Use `flex-col sm:flex-row`.
- Reduce title to `text-xl` on mobile, `text-3xl` on `sm+`.
- Move badges below the title on narrow screens.

**Flutter equivalent**: `Column` on small width, `Row` on wide — controlled by `LayoutBuilder`.

### 1.5 Breadcrumb: Collapsible on Mobile

**Problem**: `@/web/src/pages/forum/ThreadDetailPage.tsx:341-342` and `@/web/src/pages/forum/ThreadListPage.tsx:153-165` (corrected — were cited under `components/forum/...`, which doesn't exist) show full breadcrumb trail that wraps.

**Fix**:
- On mobile (`< 640px`): show only parent link + current page label. Replace intermediate items with a single "Back to Forums" link.
- Or collapse to: `< Back | Current Page Title`.

**Flutter equivalent**: `AppBar` with `leading: BackButton()` and `title: Text(...)`.

---

## Phase 2: Responsive Layout Overhaul

**Goal**: Every forum page reflows gracefully from 320px to 1440px. No horizontal scroll. No clipped content.

**Priority**: P1

### 2.1 ThreadListPage: Stacked Toolbar

**Problem**: `@/web/src/pages/forum/ThreadListPage.tsx:182-217` (corrected — was cited under `components/forum/...`, which doesn't exist) search form + sort dropdown + new thread button compete horizontally.

**Fix**:
- On mobile: stack search input (full width) on top of a row with sort dropdown (flex) + new thread button (fixed width).
- Remove `max-w-md` constraint on search on mobile.
- Make sort dropdown full-width tap target.

### 2.2 ThreadListPage: Infinite Scroll

**Problem**: `@/web/src/pages/forum/ThreadListPage.tsx` (corrected — was cited as `components/forum/...:260-278`, which doesn't exist) originally used "Previous / Page N / Next" buttons; pagination is now cursor-based with a "Load More" button (`handleLoadMore`, line 265) instead — better, but still manual rather than auto-triggered. Re-check relevance before starting.

**Fix**:
- Replace with an IntersectionObserver-based infinite scroll.
- Append next page of threads as user scrolls near the bottom.
- Show a `LoadingSpinner` skeleton at the bottom during fetch.
- Retain a "Load More" fallback button if `prefers-reduced-motion` is set.

**API impact**: `fetchThreads` already supports `page` and `limit` — no backend changes.

**Flutter equivalent**: `ListView.builder` with `NotificationListener<ScrollNotification>` or `ScrollController`.

### 2.3 ThreadDetailPage: Infinite Scroll for Posts

**Problem**: `@/web/src/pages/forum/ThreadDetailPage.tsx:140` (corrected — was cited as `components/forum/...:152`, which doesn't exist) uses a manual "Load More" button.

**Fix**:
- Same IntersectionObserver pattern as thread list.
- Reverse order if desired (newest first) or keep chronological (oldest first).
- Maintain scroll position when appending.

### 2.4 ThreadDetailPage: Floating Action Button (FAB) for Reply

**Problem**: Reply form is at the bottom of all posts. On long threads users must scroll extensively.

**Fix**:
- Add a sticky FAB in the bottom-right corner (bottom-center on mobile for thumb reach).
- Tapping FAB scrolls to the reply form and focuses the editor.
- On mobile, the reply form becomes a bottom-sheet modal that slides up over the post list.
- On desktop, inline form remains.

**Flutter equivalent**: `FloatingActionButton` + `showModalBottomSheet`.

### 2.5 SearchPage: Full-Screen Modal on Mobile

**Problem**: `@/web/src/pages/forum/SearchPage.tsx` is a dedicated page. Mobile users expect search to feel like an overlay.

**Fix**:
- Keep `/forum/search` route.
- On mobile: render search as a full-screen overlay with a top search bar, results below, and a close/done button.
- Autofocus the search input when entering.
- Show recent searches below the input (persisted in `localStorage`).

---

## Phase 3: Mobile-Native Interactions

**Goal**: Add interaction patterns that mobile users expect. These also map cleanly to Flutter.

**Priority**: P2

### 3.1 Pull-to-Refresh

**Problem**: No way to refresh content without browser chrome pull-down.

**Fix**:
- Add a pull-to-refresh gesture on thread list and thread detail (posts list).
- Use a touchstart/touchmove/scroll-top threshold or a library like `react-pull-to-refresh`.
- Show a refresh spinner and re-fetch data.
- **Backend impact**: None — uses existing `fetchThreads` / `fetchPosts`.

**Flutter equivalent**: `RefreshIndicator`.

### 3.2 Post Quote / Reply-to-Post

**Problem**: No way to reference a specific post when replying.

**Fix**:
- Add a "Reply" button to each `PostCard` (visible on all posts, not just author's).
- Tapping "Reply" opens the composer pre-filled with a blockquote of the selected post's content (truncated to 200 chars + `...`).
- Quote attribution includes author name and post timestamp.
- Backend: add `parent_post_id` or `quoted_post_id` to `CreatePostInput`.
- **Backend impact**: Light — extend `PostSerializer` and `CreatePostSerializer` with an optional `quoted_post` field. No DB migration needed if stored as JSON or a simple nullable FK.

**Flutter equivalent**: `ListTile` with trailing `IconButton(Icons.reply)`.

### 3.3 Post Action Sheet

**Problem**: No share, report, or copy-link affordances on mobile.

**Fix**:
- "More" (`⋯`) button on every post opens a bottom sheet / dropdown:
  - Share link to post (uses Web Share API if available, fallback to clipboard)
  - Copy post link
  - Report post (if not author)
  - Edit / Delete (if author/moderator)
- On desktop: dropdown. On mobile: slide-up bottom sheet.

**Flutter equivalent**: `showModalBottomSheet` with a `Column` of `ListTile` options.

### 3.4 Sticky Composer on Mobile

**Problem**: Typing a long reply on mobile causes the virtual keyboard to obscure the submit button.

**Fix**:
- When the reply form is focused, make it a fixed bottom panel that sits above the keyboard.
- Use `visualViewport` API to track keyboard height and adjust the panel position.
- Show a "Cancel" and "Post" button always visible.
- Auto-resize textarea as content grows.

**Flutter equivalent**: `TextField` with `maxLines: null` inside a bottom sheet.

### 3.5 Image Gallery / Lightbox

**Problem**: Image upload is handled inline in `TipTapEditor.tsx` (via a `forumService.ts` call) rather than a dedicated widget — this doc's original `ImageUploadWidget.tsx` reference doesn't exist. Post display still has no full-screen image viewer/lightbox.

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

### 4.1 Skeleton Loading States

**Problem**: Loading spinner is a generic spinner. Mobile users need content placeholders.

**Fix**:
- Replace `LoadingSpinner` in forum pages with skeleton cards:
  - `ThreadCardSkeleton` — gray blocks mimicking title, excerpt, metadata
  - `PostCardSkeleton` — gray avatar circle, lines for content
- Use Tailwind `animate-pulse` on skeleton elements.

**Flutter equivalent**: `Shimmer` package or `Container` with `LinearGradient` animation.

### 4.2 Draft Persistence

**Problem**: If a user navigates away while composing a reply, content is lost.

**Fix**:
- Auto-save reply content to `localStorage` every 3 seconds while typing.
- Key: `forum_draft_{threadId}`.
- Restore draft when returning to the thread.
- Clear draft on successful post.
- Show "Restore draft?" prompt if draft exists.

**Flutter equivalent**: `SharedPreferences` or `hive`.

### 4.3 Offline Post Queue

**Problem**: If connectivity drops while submitting a reply, the post is lost with an error.

**Fix**:
- On `createPost` failure (network error), store the pending post in an IndexedDB queue.
- Show a "Pending — will retry" banner with the post content grayed out.
- Retry queue when `online` event fires.
- Allow user to manually cancel/retry pending posts.

**Flutter equivalent**: `WorkManager` or custom queue with `sqflite`.

### 4.4 Image Optimization

**Problem**: Post images serve at full resolution even on small screens.

**Fix**:
- Backend already generates `thumbnail`, `large_thumbnail`, and original.
- In `PostCard`: use `thumbnail` for inline grid, `large_thumbnail` for lightbox preview, original only on explicit "view full".
- Add `loading="lazy"` and `decoding="async"` to all `<img>` tags.
- Use `srcset` for responsive image selection.

**Flutter equivalent**: `CachedNetworkImage` with different `memCacheWidth` per display size.

---

## Phase 5: Content Richness

**Goal**: Make the forum engaging and modern. These are feature additions, not fixes.

**Priority**: P3

### 5.1 @Mentions — ✅ Shipped (todo 253 slice 4)

~~**Problem**: No way to notify a specific user in a post.~~ Done: mention parsing (`wagtail_forum/mentions.py`), the `Notification` model (`wagtail_forum/models/notifications.py`), the `send_forum_mention_notification` call (`@/backend/apps/core/services/notification_service.py:411` — corrected, was cited at line 376), and composer autocomplete (`ForumMention` TipTap node in `TipTapEditor.tsx`) are all live.

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

### 5.3 Post Voting (Upvote / Downvote)

**Problem**: Reactions (`like`, `love`, `helpful`, `thanks`) are social. There's no quality signal.

**Fix**:
- Add `upvote`/`downvote` to `PostReaction` choices or a separate `PostVote` model.
- Display net score prominently on each post.
- Sort replies by score (optional per-thread setting).

### 5.4 Best Answer / Solved Marking

**Problem**: Plant problem threads have no way to mark a solution.

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

- **Playwright E2E**: `@/web/e2e/forum-authenticated.spec.js` already exists. Add mobile viewport tests (375x812).
- **Component tests**: All `*.test.tsx` files in `@/web/src/components/forum/` and `@/web/src/pages/forum/` must pass.
- **Accessibility**: Run Lighthouse CI on forum pages. Target 95+ mobile score.

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

### Phase 1 Complete When
- [ ] Edit/delete actions visible and functional on touch devices
- [ ] Reactions toggle on tap with visual feedback
- [ ] TipTap toolbar usable at 375px width without horizontal scroll
- [ ] Thread header and breadcrumb do not wrap awkwardly on mobile

### Phase 2 Complete When
- [ ] Thread list uses infinite scroll; no pagination buttons on mobile
- [ ] Post list uses infinite scroll
- [ ] Reply accessible via FAB within 2 taps from any scroll position
- [ ] Search renders as full-screen overlay on mobile
- [ ] No horizontal overflow on any forum page at 320px width

### Phase 3 Complete When
- [ ] Pull-to-refresh works on thread list and post list
- [ ] Quote/reply-to-post pre-fills composer with attribution
- [ ] Post action sheet offers share, copy-link, report, edit, delete
- [ ] Composer stays above virtual keyboard on mobile
- [ ] Image lightbox supports swipe and tap-to-close

### Phase 4 Complete When
- [ ] Skeleton loaders replace spinners on all forum lists
- [ ] Draft persists across navigation and page reloads
- [ ] Offline post queue retries automatically on reconnection
- [ ] Images use lazy loading and responsive srcset

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
| Backend lacks `PostVote` model (`TopicSubscription` now exists — 5.2 shipped) | Backend team to deliver the Phase 5.3/5.4 APIs before frontend starts those sub-phases |
| E2E test status unverified — the `todos/092-...` reference this doc cited doesn't exist (that number belongs to an unrelated, already-completed backend ticket) | Re-check current E2E status and file a fresh todo if still failing |
