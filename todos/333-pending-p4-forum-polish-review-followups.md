---
status: pending
priority: p4
issue_id: "333"
tags: [web, forum, design-system, review-followup]
dependencies: []
---

# Forum Green Thumb pass — non-blocking review follow-ups

## Problem

The bundled `/code-review` on PR #623 (forum visual pass) surfaced five
non-blocking findings. Per the review-loop budget they become this todo
instead of a third round. None affects correctness today; each is a drift
or scope risk.

## Findings

- **Stale board chrome on board→board navigation** —
  `web/src/pages/forum/ThreadListPage.tsx:72,214`: the fetch effect never
  resets `category` when `categorySlug` changes, so `/forum/A` → `/forum/B`
  renders board A's header above the list-only `ThreadListSkeleton` until
  `fetchCategory(B)` resolves. Pre-existing with `LoadingSpinner`; the
  skeleton's `withHeader` contract makes it look designed. Out of scope for
  #623 (state change).
- **Duplicated mention-dropdown class string** —
  `web/src/components/forum/forumMentionNode.ts:131,149`: the same literal in
  `onStart` and `onUpdate`; #623 had to edit both. Hoist to one constant.
- **Skeleton re-types primitive dimensions** —
  `web/src/components/forum/ForumSkeleton.tsx`: `h-[46px] w-[46px]` /
  `h-9 w-9` copy `Tile` SIZES, `h-[38px] w-[38px]` / `h-20 w-20` copy `Avatar`
  SIZES, `p-5 sm:p-6` copies `PostCard`, the hero shell copies `HeroCard`.
  A primitive change moves the loaded card but not the skeleton. Consider
  exporting SIZES from `Tile`/`Avatar` (or rendering them with a pulse
  override) and a shared hero-shell constant.
- **`Card className="rounded-lg"` stacks two radius utilities** —
  `ForumSkeleton.tsx:140`, `web/src/components/ui/HeroCard.tsx:14`,
  `web/src/pages/NotFoundPage.tsx:9`: `Card` emits `rounded-md`; the override
  relies on stylesheet order. Verify which wins in the production build
  (`npx @tailwindcss/cli`) and, if `rounded-md` wins, give `Card` a `radius`
  prop instead of a className override. The skeleton and `HeroCard` match
  either way because they use identical classes.
- **Undefined token outside the forum** —
  `web/src/components/layout/NotificationBell.tsx:139` uses `text-on-error`,
  which is not a theme token (only `on-primary`/`on-clay` exist), so the
  badge text colour is inherited. Same class of bug as the `bg-surface-1`
  fixes in #623 (`web/src/index.css:173-208` is the token list).

## Recommended Action

1. `ThreadListPage.tsx`: at the top of the slug-driven effect, `setCategory(null)`
   (or key the page on `categorySlug`) so the first-load branch renders
   `ThreadListSkeleton withHeader` for every board change. Add a test that
   navigates A→B and asserts A's name is not on screen while loading.
2. `forumMentionNode.ts`: `const DROPDOWN_CLASS = '…'` used by both branches.
3. Export `SIZES` from `Tile.tsx`/`Avatar.tsx` and import them in
   `ForumSkeleton.tsx`; pull `PostCard`'s padding and `HeroCard`'s shell
   classes into exported constants (they are components, so constants go in a
   sibling `.ts` — `react-refresh/only-export-components`).
4. Compile the CSS and settle the `rounded-lg`-on-`Card` question; add a
   `radius` prop if needed.
5. `NotificationBell.tsx:139`: `text-on-error` → `text-on-primary` (or `text-ink`),
   check both modes.

## Technical Details

See PR #623 and the review output captured in its session. Skeleton design
rationale (one `role="status"` root, fluid widths, chrome via `Card`) is in
the `ForumSkeleton.tsx` docstring — keep it true when changing dimensions.

## Acceptance Criteria

- [ ] Board A → board B shows B's header (or the header skeleton), never A's,
      while B loads — covered by a `ThreadListPage.test.tsx` case.
- [ ] One dropdown class literal in `forumMentionNode.ts`.
- [ ] `ForumSkeleton.tsx` imports its tile/avatar/padding dimensions rather
      than restating them.
- [ ] `Card` radius override resolved (prop or documented as safe) with the
      compiled-CSS evidence in the work log.
- [ ] No class in `web/src` references a colour token absent from
      `index.css` `@theme inline` (grep `surface-1|on-error|danger`).

## Work Log

### 2026-09-03 - Filed

- Filed from the `/code-review medium` pass on PR #623. The three blocking
  or trivially-fixable findings (add-reaction `min-w-11`, `SkeletonStatus`
  `aria-label`, docstring accuracy) were fixed in #623 itself.

## Notes

p4: cosmetic/maintenance. The stale-header item is the only user-visible one
and it predates #623.
