---
status: completed
priority: p4
issue_id: "433"
tags: [web, forum, premium, ai]
dependencies: []
source_review: "PR #816"
triage: ready
triaged: 2026-10-02
owner_decision: "Hide the button below 3 posts, and build the keyed latch registry (2026-09-28); 404: show a non-retrying 'thread unavailable' message only, no per-account latch (2026-10-02)"
---

# Thread summary panel: non-blocking review findings

## Problem

The bundled `/code-review` of PR #816 (todo 414) raised these. None was
blocking, so under the two-round review budget they land here.

## Findings

- **Button on too-short threads.** The page already has `thread.post_count`.
  Below 3 posts every click spends a 30/h slot to learn `too_short`. Hide or
  disable the button there.
- **`throttledMessage` rounds to minutes with no plural** ("about 1
  minutes"), and duplicates `describeWait()` in
  `NewGroupConversationForm.tsx`. Share one formatter.
- **A 404 (topic unpublished or moved to a restricted board) says "try
  again"**, and each retry spends a slot. Treat 404 as non-retryable.
- **`readRetryAfterSeconds` copies `messageService.readRetryAfter`.** Export
  one.
- **Third copy of the capability latch + error class** (compose assist, RAG,
  thread summary), each with its own manual reset line in `AuthContext`. A
  keyed latch registry with one reset-all removes the "forgot to add the
  reset" failure mode.
- **Polls keep firing while the tab is hidden**, against the
  `docs/rules/react.md` polling rule. Skip the tick while
  `document.visibilityState === 'hidden'`.

- **Same 401 latch in plant-care ask** (round 2). `RagError.permanent`
  (`forumService.ts`, used by `PlantCareAskPanel`) includes 401 on purpose,
  because that page is public and a 401 teaches an anonymous visitor. For a
  SIGNED-IN user it is the same expired-cookie bug #816 fixed: latch 401 only
  when there is no signed-in user.

## Acceptance Criteria

- [x] Each finding is fixed with a test, or explicitly declined with a reason.

## Work Log

### 2026-09-24 - Filed from PR #816 review round 1

### 2026-10-02 - Implemented by the todo sweep (run 2026-10-02-0335)

- Finding 1, button on too-short threads (owner: hide below 3), fixed with a
  test: `ThreadSummaryPanel` takes a required `postCount`, renders the "needs
  at least 3 posts" line instead of the button below `MIN_POSTS`, and keeps
  the server's `too_short` branch for the race. `ThreadDetailPage` passes
  `totalPosts + 1`: `Thread.post_count` is the API's `reply_count` (opener
  excluded, `forumMappers.ts`), while the server's `too_short` counts every
  live post INCLUDING the opener (`build_summary_source`). Tests: panel 'does
  not offer the button below 3 posts, says why, and offers it once the thread
  grows'; page 'hides Summarize thread below 3 posts and offers it from the
  third (todo 433)', which pins the +1 from both sides (one reply hidden, two
  replies offered).
- Findings 2 and 4, the unpluralised `throttledMessage` duplicating
  `describeWait`, and `readRetryAfterSeconds` copying
  `messageService.readRetryAfter`, fixed with tests: both lifted into
  `web/src/utils/retryAfter.ts`; `messageService`, `forumService`,
  `NewGroupConversationForm` and `ThreadSummaryPanel` import them. Tests:
  `retryAfter.test.ts` (every reader form, including a response with no
  `Headers` object; wait text from 1 s to 3600 s) and the panel's 'pluralizes
  the throttled wait' (60 s "about 1 minute", 90 s "about 2 minutes"); the
  existing "about 60 minutes" assertion still holds.
- Finding 3, 404 says "try again" (owner: a non-retrying 'thread unavailable'
  message only, no per-account latch), fixed with a test: a `TopicSummaryError`
  404 sets the panel-local `unavailable`, shows "This thread is unavailable,
  so it cannot be summarized." and never calls `markTopicSummaryUnavailable`.
  Test: 'on 404 (topic gone or restricted) says the thread is unavailable,
  offers no retry, and does not latch' — the service latch stays false and a
  fresh mount offers the button.
- Finding 5, third copy of the latch (owner: keyed registry), fixed with a
  test: `web/src/services/capabilityLatch.ts` holds one `Set<CapabilityKey>`
  with `is/mark/reset(key)` and `resetAllCapabilityLatches()`; the six
  `forumService` functions are thin wrappers over it (kept on purpose: the
  components and some 36 call sites, mostly tests, read better as a sentence
  than as a key, and churning them buys nothing); `AuthContext` calls only
  `resetAllCapabilityLatches()`, so a new capability cannot be forgotten
  there. Tests: `capabilityLatch.test.ts`; `AuthContext.test.tsx` 'clears the
  compose-assist latch when the identity changes' passes unchanged through
  the wrappers. The "+ error class" half is declined: `ComposeAssistError`,
  `RagError` and `TopicSummaryError` each encode a different `permanent`
  contract (403 only; 401/403/disabled; 403 with `retryAfter`) and callers
  branch on `instanceof`, so a shared base would add a layer without removing
  a decision.
- Finding 6, polls while hidden, fixed with tests: after each poll delay the
  loop awaits `document.visibilityState !== 'hidden'` through a one-shot
  `visibilitychange` listener that unmount removes and resolves; hidden time
  is a wait, not a poll, so it spends no slot and does not count toward
  `MAX_POLLS`. Tests: 'waits for the tab to be visible before the next poll,
  spending none of the poll budget while hidden' and 'abandons a hidden-tab
  wait on unmount instead of polling when the tab returns'.
- Finding 7, the same 401 latch in plant-care ask, fixed with a test:
  `PlantCareAskPanel` reads `useAuth().isAuthenticated`; a signed-in 401 shows
  "Your session expired. Sign in again to ask about plant care.", keeps the
  form usable and does not latch, while the anonymous 401 still latches and
  `RagError.permanent` is unchanged. Test: 'on a 401 for a SIGNED-IN user says
  the session expired, keeps the form, and never latches (todo 433)'; the
  panel test now mocks `useAuth` (anonymous by default), as `SearchPage.test`
  — the page that hosts the panel — already did.

### 2026-10-02 - Verified by the todo sweep (run 2026-10-02-0335)

- AC 1: `cd web && npx vitest run --reporter=verbose src/components/forum/ThreadSummaryPanel.test.tsx src/components/forum/PlantCareAskPanel.test.tsx src/services/capabilityLatch.test.ts src/utils/retryAfter.test.ts src/contexts/AuthContext.test.tsx src/pages/forum/ThreadDetailPage.test.tsx src/services/messageService.test.ts src/components/forum/NewGroupConversationForm.test.tsx src/services/forumService.test.ts src/components/forum/TipTapEditor.test.tsx src/pages/forum/SearchPage.test.tsx` — evidence `.sweep-evidence/g2/433-ac0.txt` (not committed), last lines:

  ```text

   Test Files  11 passed (11)
        Tests  356 passed (356)
     Start at  05:47:12
     Duration  5.26s (transform 1.83s, setup 1.61s, import 6.24s, tests 12.54s, environment 7.99s)
  ```

### 2026-10-02 - Completed by the todo sweep (run 2026-10-02-0335)

- Archived by `land.py archive`; evidence is quoted above, review is on the PR.
