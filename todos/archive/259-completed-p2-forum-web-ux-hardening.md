---
status: completed
priority: p2
issue_id: "259"
tags: [forum, web, react, a11y]
dependencies: []
source_review: "docs/audits/2026-07-11-forum-modernization.md"
source_finding: "H18, M22, M24, M25, M26, M27, M29, M30, M31, L2, L4, L10, L11, L12, L13"
---

# Forum epic: web UX & a11y hardening

## Problem

The web forum's interaction quality is below professional-forum par: no retry
affordance on any error, unguarded fetch races, native `alert()/confirm()/prompt()`
dialogs, silently-ineffective live regions app-wide, focus drops after posting,
unsaved-edit loss, and a cluster of composer/navigation/a11y gaps. p2 epic from
the 2026-07-11 forum-modernization audit; carries the M32 renderer-tightening
residue.

## Findings

All paths under `web/src` unless noted.

- **H18** — No retry affordance on any forum error state — all 4 pages render a
  static error box; only recovery is a full reload (`pages/forum/*`:
  CategoryList:49, ThreadList:143, ThreadDetail:258, NewThread:105).
- **M22** — Data-fetch effects lack unmount/race guards (no cancelled flag, 3
  pages) — fast navigation can render thread A's content under thread B's URL.
  Research: react.dev prescribes the `ignore` cleanup flag as PRIMARY
  (AbortController alone documented insufficient).
- **M24** — Native dialogs inconsistently: `alert()` for pending-moderation on
  new thread (identical outcome uses a styled banner for replies), `confirm()`
  for delete, `prompt()` for link URL with no validation.
- **M25** — Focus drops after posting a reply: remount-via-key clears cleanly
  but the fresh editor is never focused and no success announcement fires.
- **M26** — Write-path banners have no working `role="alert"` — SCOPE IS
  APP-WIDE by research: all 8 existing `role="alert"` sites (incl. TipTapEditor,
  `Input.tsx:81`, LoginPage:161) use the conditional-mount-with-content
  anti-pattern MDN documents as generally NOT announced. Fix = persistent
  live-region container whose text content swaps.
- **M27** — Clicking Edit on a second post silently discards unsaved edits on
  the first (single `editingPostId`/`editBody` state, no dirty check).
- **M29** — No client-side file size/type pre-check before image upload; no
  max-size hint.
- **M30** — No jump-to-page/jump-to-latest in long threads; the two Load More
  buttons are inconsistent (list shows bare "Load More" because `meta.count` is
  hardcoded 0 in the service).
- **M31** — No scroll-to-top on forum navigation — `useHandlePageChange` exists
  and is used by Search/Blog pages, just not wired here.
- **L2** — Onboarding/empty states bare; `ForumIndex.intro` CMS field never
  serialized so welcome copy can't reach the UI; board list lacks last-activity.
- **L4** — No markdown input path; NewThreadPage requires `?category=` — no
  board picker in the composer. (Assigned to this epic at Phase 4 finalization —
  unassigned in the draft grouping.)
- **L10** — Composer toolbar buttons ~32px vs the project's 44px tap-target
  rule (WCAG 2.5.5 AAA — a voluntary project bar, applied elsewhere).
- **L11** — `Button` never sets `aria-busy` and the label doesn't change during
  submit. Research: label-swap ("Posting…") is the reliable primary signal.
- **L12** — Absolute timestamps hover-only (`title`) — inaccessible on touch
  and to screen readers; fix = `<time datetime>` + aria-label.
- **L13** — Composer/upload tests tautological ("provides onChange" asserts the
  mock is defined); `handleImageSelect` paths uncovered.
- **M32 residue** (finding owned by manifest, tests landed at audit): the
  renderer's `includes('<')` quote heuristic + broad STREAMFIELD DOMPurify
  preset (h1-h6/pre/img/div ≫ forum nh3 allowlist) should be tightened to the
  forum contract (`components/StreamFieldRenderer.tsx:31-37,110`,
  `utils/sanitize.ts:114-139`). Contract tests from the audit pin current
  behavior — tighten against them.

## Recommended Action

Batch by surface, each independently shippable:

1. **App-wide announcement infra** (M26): persistent live-region container
   (content-swap pattern), migrate the 8 broken `role="alert"` sites; add
   Button busy signal (L11) and `<time>` timestamps (L12) in the same a11y pass.
2. **Fetch discipline** (M22, H18): `ignore`-flag cleanup on the 3 pages +
   Retry button on every error state.
3. **Dialog + editing safety** (M24, M27, M25): styled confirm/notice
   components replace native dialogs; dirty-check before switching edit
   targets; autofocus + success announcement after posting.
4. **Composer** (M29, L4, L10, L13, M32 residue): pre-upload size/type check
   with hint; board picker in NewThreadPage; 44px targets; real tests for
   `handleImageSelect` success/failure; tighten quote rendering to the forum
   allowlist.
5. **Navigation polish** (M30, M31): wire `useHandlePageChange`; honest
   Load More labels (fix `meta.count`); jump-to-latest.
6. **Empty states** (L2): serialize `ForumIndex.intro`, richer empty/onboarding
   copy, last-activity on board cards.

## Technical Details

- MDN alert-role guidance drives M26: the live region must exist in the DOM
  before content changes; swap `textContent`, don't conditionally mount.
- M32 tightening must keep the audit's contract tests green (script/onerror
  neutralization in string-shaped quotes; heading/code React-escaped).
- Follow `web/docs/patterns/react-typescript.md` + `tailwind.md` (44px rule).

## Acceptance Criteria

- [x] A failed post/moderation notice is announced by a screen reader
      (persistent live-region, tested via content-swap not conditional mount)
      — `AnnouncerContext` (persistent aria-live, content-swap test) + ThreadDetailPage
      persistent notice banner; `AnnouncerContext.test.tsx` asserts the region is
      the SAME node before/after (content swap, not remount).
- [x] All forum fetches race-guarded; every forum error state has a working
      Retry — react.dev `ignore` cleanup on CategoryList/ThreadDetail/NewThread
      (ThreadList already had loadGenRef); shared `ForumErrorState` retry (H18),
      CategoryListPage retry test proves recovery.
- [x] No native `alert/confirm/prompt` in forum flows — ConfirmDialog (delete),
      NewThreadPage confirmation panel (was alert), PostCard inline reveal (was
      prompt), TipTapEditor styled link editor (was prompt); tests assert
      `window.alert/confirm/prompt` not called.
- [x] Switching edit targets with unsaved changes prompts; reply flow restores
      focus and announces success — M27 dirty-check → ConfirmDialog (tested);
      reply autofocus (TipTap `autofocus`) + `announce('Reply posted.')` (tested).
- [x] Composer: client-side pre-upload validation with visible limits, board
      picker, ≥44px toolbar targets, non-tautological upload tests — TipTapEditor
      type/size pre-check + limits hint (M29), 44px targets (L10), NewThreadPage
      board picker (L4), real handleImageSelect success/failure/reject tests (L13).
- [x] Quote blocks render under the forum allowlist (audit contract tests
      still green) — forum content (paragraphs) sanitized under the tightened
      `FORUM` preset matching nh3 (M32); the audit's quote XSS + heading/code
      contract tests remain green (verified in the full run).
- [x] Scroll-to-top wired on forum routes; Load More counts honest — `useScrollToTop`
      on the 4 core forum pages (M31); ThreadListPage Load More shows honest
      `(N remaining)` from board.topic_count, service no longer hardcodes count (M30).

## Work Log

### 2026-07-11 - Created from forum-modernization audit (Phase 4 deferral)

- Epic groups 15 open findings (incl. L4, unassigned in the draft grouping —
  added here at finalization) + the M32 renderer residue.

### 2026-07-24 - Started by completing-todos skill (run 2026-07-24-2133)

- Picked up by automated workflow.

### 2026-07-24 - Implemented in 5 batched surfaces (branch forum-web-ux-hardening-259)

- **S1** (5a72acb) M26/L11/L12 → AC1: `AnnouncerContext` persistent live region,
  Button aria-busy + loadingText, `<Timestamp>` (`<time datetime>` + aria-label).
- **S2** (afff240) M22/H18 → AC2: react.dev `ignore` race guards + shared
  `ForumErrorState` Retry.
- **S3** (2a68a9d) M24/M27/M25 → AC3/AC4: `ConfirmDialog`, NewThread confirmation
  panel, PostCard inline copy reveal, TipTap link editor; edit dirty-check; reply
  autofocus + success announce.
- **S4** (728aacc) M29/L10/L4/L13/M24/M32 → AC5/AC6: image pre-check + hint, 44px
  targets, board picker, real upload tests, tightened `FORUM` sanitizer allowlist.
- **S5** (d587240) M31/M30 → AC7: `useScrollToTop`, honest Load More counts.
- **Verification** (all green, quoted):
  - `npx vitest run` → `PASS (692) FAIL (0)` (added ~23 real tests incl. the M32
    contract + content-swap-announce + upload success/failure).
  - `npm run type-check` → `tsc --noEmit` (0 errors).
  - `npm run lint` → `ESLint: 0 errors, 1 warnings` (the 1 warning is in the
    generated coverage artifact `block-navigation.js`, not source).
- **Scope decision**: L2 (empty states / `ForumIndex.intro` CMS serialization,
  last-activity on board cards) and the app-wide M26 role="alert" migration
  beyond forum flows (Input.tsx, LoginPage) are DEFERRED — L2 is an "L", in no
  AC, and drags in backend Wagtail work; spun out to follow-up todo 278. AC gate
  fully met without them.

### 2026-07-24 - Code review + repair

- Ran bundled `/code-review` (high effort, 8-angle bug pass) + `code-review-orchestrator`
  (checklist). Both independently flagged the same one real defect: `ConfirmDialog`
  restored focus to the confirm button (unmounting) instead of the trigger on
  close, because a React `autoFocus` prop fires during commit before the
  focus-capture effect (WCAG 2.4.3). **Repaired** (34ed3cb): capture the trigger
  first, focus the confirm button via ref; also made aria ids unique per instance
  (useId). Added a focus-in/focus-return test. No other critical/high findings;
  the sanitizer routing, race guards, and announcer pattern were confirmed sound.
- Final: `npx vitest run` → `PASS (693) FAIL (0)`; type-check + lint clean.

### 2026-07-24 - Completed by completing-todos skill (run 2026-07-24-2133)

- Verification: all 7 acceptance criteria passed (backed by 693 green web tests,
  clean tsc + eslint).
- Review: bundled `/code-review` (high) + `code-review-orchestrator`; 1 real
  finding (ConfirmDialog focus-return), repaired (34ed3cb); no critical/high left.
- Codified: LEARNINGS (autoFocus-vs-useEffect focus timing) + react-typescript
  pattern (persistent live-region announcer) — d0d9123.
- Audit `## Finding Status`: all 14 of 259's findings checked off; L2 re-pointed
  to follow-up todo 278 (deferred: empty states + app-wide role="alert" sweep).

## Notes

p2. Largest epic by count but mostly small, batchable fixes — good
milestone-between-features material.
