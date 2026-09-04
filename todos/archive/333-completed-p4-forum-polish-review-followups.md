---
status: completed
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

- [x] Board A → board B shows B's header (or the header skeleton), never A's,
      while B loads — covered by a `ThreadListPage.test.tsx` case
      ("drops board A's header while board B loads…"); the case fails against
      the code without the reset (mutation check quoted below) (2026-09-04)
- [x] One dropdown class literal in `forumMentionNode.ts` — `DROPDOWN_CLASS`;
      the literal occurs once (2026-09-04)
- [x] `ForumSkeleton.tsx` imports its tile/avatar/padding dimensions rather
      than restating them — from `ui/dimensions.ts`, which `Tile`, `Avatar`,
      `PostCard` and `HeroCard` also consume (2026-09-04)
- [x] `Card` radius override resolved (prop or documented as safe) with the
      compiled-CSS evidence in the work log — `radius` prop; compiled CSS
      proves `.rounded-md` was winning (2026-09-04)
- [x] No class in `web/src` references a colour token absent from
      `index.css` `@theme inline` (grep `surface-1|on-error|danger`) —
      `on-error` is now a defined token; grep + a stem audit quoted below
      (2026-09-04)

## Work Log

### 2026-09-04 - Started by completing-todos skill (run 2026-09-04-0350)

- Picked up by automated workflow, in worktree `feat/forum-polish-followups`.

### 2026-09-04 - Implemented (run 2026-09-04-0350)

1. **Stale board chrome.** `ThreadListPage`'s load effect now resets
   `category` and `threads` when the resolved board id differs from the
   cached one (a sort/tag change on the same board keeps the chrome). The new
   test swaps the mocked `useParams` value and re-renders; it asserts no
   heading named for board A and a `role="status"` skeleton while B's fetch
   is pending, then B's heading once resolved.
2. **Dropdown class.** `DROPDOWN_CLASS` in `forumMentionNode.ts`; both
   `onStart` and `onUpdate` assign it.
3. **Skeleton dimensions.** New `web/src/components/ui/dimensions.ts`
   (`TILE_BOX`/`TILE_RADIUS`, `AVATAR_BOX`/`AVATAR_RADIUS`,
   `POST_CARD_PADDING`, `HERO_CARD_PADDING`). A `.ts` sibling because `.tsx`
   component files may export only components
   (react-refresh/only-export-components). Box and radius are split so a
   `SkeletonBlock` takes the box while its `rounded` prop takes the
   primitive's radius (`tile-md`, `avatar-lg`, …) — never two `rounded-*`
   utilities on one element. Side effect: the skeleton's tile/avatar corners
   now match the primitives (14px/12px, not the 10px token) — more faithful,
   not less.
4. **Card radius.** Compiled CSS (`vite build`) emits `.rounded-lg` at byte
   22523 and `.rounded-md` at 22566 — `rounded-md` wins, so every
   `<Card className="rounded-lg">` (HeroCard, NotFoundPage, the skeleton
   hero) had been rendering at the md radius. `Card` gained
   `radius?: 'md' | 'lg'` (default md); the three sites use the prop. This
   is a visible change: hero cards and the 404 card now render at 22px as the
   design intended.
5. **`text-on-error`.** The todo suggested `text-on-primary`; that is
   correct by coincidence only. Error red is the salmon `canopy-red` in dark
   mode (dark text reads) and the deep `#a63c2a` in light mode (light text
   reads) — the same flip `on-clay` already documents. Defined
   `--gt-on-error` per mode (abyss / `#f2faf4`, both ≈5.8:1) and registered
   `--color-on-error` in `@theme inline`, so the badge keeps its semantic
   class and the token exists in both modes.

Verification:

```
$ tsc --noEmit                       → exit 0
$ eslint --max-warnings 0 <14 files> → exit 0
$ prettier --write <15 files>        → all formatted
$ vitest run
 Test Files  89 passed (89)
      Tests  1052 passed (1052)
$ vite build → compiled CSS contains
  .text-on-error{color:var(--gt-on-error)}
  .rounded-\[11px\]/.rounded-\[12px\]/.rounded-\[14px\]/.rounded-\[16px\]{border-radius:…}
  .rounded-lg (offset 22523) before .rounded-md (22566)
$ rg "surface-1|on-error|\bdanger\b" src → only index.css's on-error definitions
  and NotificationBell.tsx:139's use of it
$ stem audit (every text-/bg-/border-/ring-… stem in src/**/*.tsx vs @theme inline)
  → no colour stem outside the 26 tokens (leftovers are border-b, text-base,
  ring-offset-2 and the like)
```

Mutation check — the navigation test is not hollow:

```
$ (reset block removed) vitest run ThreadListPage.test.tsx -t "drops board A"
AssertionError: expected <h1 class="gt-h1 text-ink"></h1> to be null
 Tests  1 failed | 22 skipped (23)
$ (restored) → 23 passed
```

### 2026-09-04 - Review round 1 (bundled `/code-review medium`, run 2026-09-04-0350)

Eight findings. Repaired in this slice:

1. **CONFIRMED bug I introduced — cache-hit path never re-set `category`.**
   A → B (reset nulls the state) → back to A before B resolves: A is served
   from `categoryCacheRef`, the `if (!categoryData)` branch is skipped, so
   `setCategory` never ran and the page rendered with an empty `h1`, no tile,
   `category!` stamped as null onto Load More rows. Fix: `setCategory(categoryData)`
   unconditionally after resolution. Test: "restores the cached board header
   when navigating back before the new board resolves".
2. **Threads-fetch failure after the category resolved showed the empty-board
   copy.** Pre-existing, but the new `setThreads([])` made it the guaranteed
   outcome on board navigation. Fix: the threads slot renders
   `ForumErrorState` when `error` is set. Test: "shows the error state, not
   an empty board, when the category loads but the threads fetch fails".
3. **Binding rule + trigger contradicted the diff.** `docs/rules/react.md`
   and the `tailwind-undefined-color-token` trigger in
   `docs/rules/triggers.json` still asserted `on-error` does not exist, so the
   harness would have warned on every edit of `NotificationBell.tsx`. Both
   updated; `scripts/inject` tests 118 passed.
4. **`POST_CARD_PADDING` was wired to the blocked-post stub only** (my exact
   match hit line 140, not the real shell at 208). Fixed at the real shell.
5. **Three more `bg-error text-white` buttons** (MyPlantsPage,
   DiagnosisListPage, DiagnosisDetailPage) — the exact case the token exists
   for; swapped to `text-on-error` (identical in light mode, readable in dark).
6. `AVATAR_RADIUS.lg` was `rounded-[16px]`, an arbitrary twin of
   `--radius-md: 16px` → `rounded-md`.
7. Community-experts rail avatar hand-rolled `h-[34px] w-[34px]
   rounded-[11px]` → `AVATAR_BOX.sm`/`AVATAR_RADIUS.sm` (its presence dot
   differs from `Avatar`'s, so not a full component swap).

**Known issues (accepted, LOW):** the header-skeleton early return unmounts
the main layout on a board→board hop, re-issuing the rail's
`fetchPopularPosts` and dropping typed search text. The todo's own
recommended fix (`setCategory(null)` / keying on the slug) has the same
effect; rendering the header skeleton inline would be a larger refactor than
this slice warrants. Reachable only via CommandPalette or history navigation
at ≥1280px.

Verification after the fixes (the machine was under a load average of
90–124 from a concurrent Xcode archive, so the full run is in pieces):

```
$ tsc --noEmit → exit 0; eslint --max-warnings 0 <8 files> → exit 0; prettier → unchanged
$ vitest run  (full, under load)
 Test Files  4 failed | 84 passed (88)      ← 4 × "Test timed out in 10000ms",
      Tests  4 failed | 1039 passed (1043)     1 file's fork worker never started
$ vitest run AuthContext PollCard ThreadDetailPage BlogDetailPage   (the 4 timeouts, idle)
 Tests  110 passed (110)   Duration 3.27s
$ vitest run CategoryCard.test.tsx   (the file whose worker never started)
 Tests  11 passed (11)
→ 1043 + 11 = 1054 tests, every file green; baseline was 1047 (+7 new).
$ python -m pytest scripts/inject → 118 passed, 171 subtests passed
```

### 2026-09-04 - Review round 2 (react-typescript-reviewer, verification only)

All three behavioural fixes hold on hand-trace against the pre-fix diff;
`PostCard.tsx` and `CommunityExpertsModule.tsx` confirmed byte-identical
class output. Three LOW notes:

- Two test-strictness gaps, both taken: the A→B→A test now pins
  `fetchCategory` to exactly two calls (A served from the cache, never
  re-fetched); the threads-fail test re-asserts the board heading after the
  error text so header and error are proven to coexist.
  `ThreadListPage.test.tsx`: 25 passed after the tweaks.
- **Known issue (pre-existing, accepted):** a valid board followed by an
  *invalid* URL (`/forum/not-a-board`) returns early before the reset, so
  the previous board's header can sit above "Invalid category URL", and a
  slow in-flight load for that board can clear the error. Not introduced
  here; noted for whoever next touches the slug-parse branch.

### 2026-09-04 - Completed by completing-todos skill (run 2026-09-04-0350)

- Verification: all 5 acceptance criteria passed (evidence quoted inline
  above), plus the mutation check on the board-navigation test.
- Review: round 1 — 8 findings (7 repaired, 1 LOW accepted); round 2 —
  fixes verified, 2 LOW test tweaks taken, 1 LOW pre-existing accepted. No
  blocking findings remain.
- Shipped as a PR from worktree branch `feat/forum-polish-followups`
  (deviation from the skill's never-commit rail, per the project's
  "a todo slice ships as a merged PR" convention).

### 2026-09-03 - Filed

- Filed from the `/code-review medium` pass on PR #623. The three blocking
  or trivially-fixable findings (add-reaction `min-w-11`, `SkeletonStatus`
  `aria-label`, docstring accuracy) were fixed in #623 itself.

## Notes

p4: cosmetic/maintenance. The stale-header item is the only user-visible one
and it predates #623.
