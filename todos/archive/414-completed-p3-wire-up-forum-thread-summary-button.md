---
status: completed
priority: p3
issue_id: "414"
tags: [web, forum, ai]
dependencies: []
source_review: "todos/archive/405-completed-p3-backend-endpoints-no-client-triage.md"
source_finding: "owner decision 2026-09-23"
---

# Add the premium "Summarize thread" button on web (`forum/topics/<id>/summary/`)

## Problem

`GET forum/topics/<id>/summary/` (`apps/forum_host/summary.py`; 20 tests;
`IsPremiumUser`, throttled) is finished. It is the only premium AI feature with
no UI: compose-assist and care/ask are wired at
`web/src/services/forumService.ts:827,915`. Its design spec says the UI belongs
to a later wave (`docs/superpowers/specs/2026-07-22-forum-thread-summarization-design.md:26,32`).
The owner decided (todo 405) to wire it up.

## Findings

Evidence is recorded in todo 405's 2026-09-23 Work Log. It came from a
`get_resolver()` route walk, client greps, and an adversarial verifier that ran
the endpoints against a test DB.

## Recommended Action

1. Add a service call and a premium-only button on `ThreadDetailPage`.
2. Handle the loading, error, throttled (429) and non-premium states.
3. Add tests.

## Technical Details

See the file references above, and todo 405's Work Log.

## Acceptance Criteria

- [x] A premium user sees and can run a summary; a non-premium user sees nothing, or an upsell.
- [x] Tests cover the 429 and 403 paths.

## Work Log

### 2026-09-23 - Filed from todo 405

The owner decided, during the endpoint triage, to wire this up rather than
remove it.

### 2026-09-24 - Done: premium Summarize-thread panel on ThreadDetailPage

**Backend contract (read from `apps/forum_host/summary.py`, `tasks.py`,
`api_urls.py`, `tests/test_summary.py`, `apps/core/exceptions.py`):**
`GET /api/v1/forum/topics/<id>/summary/` → 200 `{status:"ready", summary,
post_count, generated_at}` · 200 `{status:"too_short", post_count}` · 202
`{status:"pending"}` (Celery generates; the client must poll) · 401 anon · 403
non-premium (`message: "This feature requires a premium account."`) · 404
restricted/missing · 429 `code: rate_limit_exceeded` + `Retry-After`. There is
**no 503/disabled path** — the endpoint has no feature flag. The 30/h
`topic_summary` bucket counts every poll, and a generation skipped for an
exhausted global AI budget never lands, so polling must be bounded.

**Premium gating decision:** the web cannot know premium in advance — neither
the `User` type nor `UserProfileSerializer` (`/auth/user/`) carries
`is_premium`/`has_premium_access`. So this mirrors compose-assist and
plant-care ask: signed-in users see the panel (labelled "AI · Premium"); the
server's 401/403 latches `isTopicSummaryUnavailable()` in `forumService` for
the session. The panel that got the 403 shows the server's premium message in
place of the button (the upsell); every later mount renders nothing.
`AuthContext` clears the latch on identity change. Exposing a premium flag on
the user payload was deliberately NOT done (backend scope expansion).

**Shipped:** `fetchTopicSummary` + `TopicSummaryError` (status, code,
`retryAfter`, `permanent` = 401/403) + latch in `web/src/services/forumService.ts`;
`TopicSummary` union in `types/forum.ts`; `components/forum/ThreadSummaryPanel.tsx`
(poll every 5s, max 6 polls, then "still being written — try again"; 429 →
"summary limit … try again in about N minutes" from Retry-After; too_short;
generic error; summary rendered as text; timer in `useRef`, run token stops an
in-flight run on unmount); mounted in `ThreadDetailPage` under
`isAuthenticated && topicId != null`, `key={topicId}`.

**Tests (TDD, each written first and seen red):**
- `forumService.test.ts` +4: URL `/topics/12/summary/` GET with cookie auth;
  202 pending / too_short are results; 401/403 permanent, 429 reads
  Retry-After 3600, 404/500 transient; unknown status / blank ready rejected.
  Red before implementation: 4 failed | 62 passed.
- `ThreadSummaryPanel.test.tsx` (new, 9): premium path renders summary;
  pending→poll→ready; bounded at 1+6 requests; 429 throttled message keeps
  button, no latch; 403 hides button, shows premium notice, latches, remount
  renders nothing; too_short; generic 500; unmount stops polling; in-flight
  request resolving pending after unmount does not start polling.
  Red before component: suite failed to resolve the module.
- `ThreadDetailPage.test.tsx` +3: signed-in user runs summary (called with 12);
  logged-out sees no button; latched account sees no panel. The signed-in test
  was red before wiring (1 failed | 2 passed).
- `AuthContext.test.tsx`: the existing latch test also asserts the summary
  latch clears on identity change — red with the reset call deleted, green
  restored.

**Mutation checks (backup copy → mutate → run → restore by copy; all went red):**
M1 drop 429 branch → 429 test red · M2 drop 403 latch branch → 403 test red ·
M3 drop mount-time latch return → panel 403 test + page latched test red ·
M4 drop poll cap → bounded-poll test red · M5 drop unmount run-token bump →
initially SURVIVED (clearTimeout alone covered the timer path); added the
in-flight-at-unmount test, now red · M6 401 not permanent → service red ·
M7 drop Retry-After → service red · M8 wrong URL → service red · M9 accept
blank ready → service red · M10 drop isAuthenticated gate → page logged-out
test red · M11 treat pending as final → 2 panel tests red.

**Verification (web/):** `npm run type-check` clean · `npm run lint` clean ·
`npx vitest run` on the 6 touched/adjacent files: 262 passed · full
`npx vitest run`: 103 files, 1412 passed · `npm run check:classes`: 134 files,
5766 tokens, exit 0 · prettier --check clean on all touched files.
