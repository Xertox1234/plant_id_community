---
status: completed
priority: p3
issue_id: "297"
tags: [web, auth, react]
dependencies: []
---

# Web SPA never revalidates the logged-in identity

## Problem

The React app caches the logged-in user (sessionStorage + in-memory context)
and never re-checks it. If the cookie-jar identity changes in another tab
(re-login as a different account), the header keeps showing the old user while
the server attributes every write to the new cookie identity — the UI and the
actual acting account silently diverge.

## Findings

- Live incident on prod 2026-08-13: the header showed `test-user5`, but a
  forum reply was created as `plantadmin` (server-verified via the API) —
  the session cookie had been switched in another tab of the same Chrome
  profile (one cookie jar per profile). The misattributed post had to be
  cleaned up. Recorded in memory `project_web_auth_jwt_cookie_bug` (satellite
  finding 2).
- `web/src/services/authService.ts` stores the user object in sessionStorage
  after login and the auth context serves it from memory; nothing refetches
  `/api/v1/auth/user/` after the initial load.

## Recommended Action

1. Revalidate identity on `window` `focus` (and/or `visibilitychange` →
   visible): refetch `GET /api/v1/auth/user/` with credentials and reconcile —
   if the username differs from the cached identity (including logged-out
   401), update the auth context and sessionStorage immediately.
2. Defense-in-depth on writes: forum/blog write responses include the author;
   if the response author's username differs from the displayed user, force an
   identity refresh and surface a notice instead of rendering the optimistic
   state.
3. Debounce the focus refetch (e.g. at most once per 30s) so tab-switching
   doesn't spam the API.

## Technical Details

- `web/src/services/authService.ts` — login/user caching (sessionStorage,
  "cleared on tab close").
- Auth context/provider under `web/src/` (identity consumer for the header).
- Gotcha reminder for the implementation: debounce/timer IDs in React go in
  `useRef`, not `useState` (root CLAUDE.md gotcha 5).

## Acceptance Criteria

- [x] Repro scenario fixed: log in as user A, re-log-in as user B in a second
      tab, focus the first tab → header shows user B without a manual reload.
- [x] A write made with a switched cookie identity either posts under the
      displayed user or forces the identity refresh — it can no longer render
      as if authored by the stale user.
- [x] Vitest coverage for the focus-revalidation path (mocked fetch identity
      change → context update).

## Work Log

### 2026-08-13 - Filed

- Filed from live prod testing findings (misattributed-post incident).

### 2026-08-17 - Started by completing-todos skill (run 2026-08-17-0246)

- Picked up by automated workflow.

### 2026-08-17 - Implemented

**Scope correction (verified before implementing, not assumed):** Recommended
Action #2 claims "forum/blog write responses include the author" — false.
Read the actual backend views: `TopicListView.post()` and `PostListView.post()`
(`backend/packages/wagtail_forum/wagtail_forum/api/views.py`) both return only
`{id, slug/status}` — no author field. Adding one would mean a multi-file
backend change (2 response shapes + the idempotency `remember()` payload + 2
`@extend_schema` updates + package/host tests) for a todo whose own Technical
Details names only web files. Called `advisor` on this before proceeding —
confirmed AC2's actual wording is an *outcome* ("can no longer render as if
authored by the stale user"), not the *mechanism* Recommended Action #2
proposed, and a post-write `getCurrentUser()` reconciliation satisfies the
outcome with zero backend change (a pre-write check is a TOCTOU race that
can't be won client-side anyway — post-write detection is the only sound
approach). Scoped AC2 to the two content-create call sites
(`NewThreadPage`/`ThreadDetailPage` — where "renders as if authored by the
stale user" is a real, user-visible outcome); reactions, bookmarks,
subscriptions, and solution-marking don't render authorship, so wrapping
every `forumService` write would be the todo-284 cross-cutting-sprawl trap
in miniature.

**AC1 — focus revalidation** (`web/src/contexts/AuthContext.tsx`):
- New `useEffect` (mounted unconditionally, not gated on `user`, so both
  directions work: already-authed picking up a switch, and logged-out
  picking up a login elsewhere) listening for `window` `focus` and
  `document` `visibilitychange` → `visible`.
- Debounced via a `useRef` timestamp (gotcha 5 — not `useState`), gap set
  before the `await` so a `focus` event and its immediately-following
  `visibilitychange` collapse into one fetch, not two.
- Reconciles via `authService.getCurrentUser()` (already returns `null` on
  401 — no special-casing needed for "including logged-out") +
  `setUser((prev) => ...)`, returning `prev` unchanged when the username
  matches, so an alt-tab with no identity change doesn't force a re-render.
- Deliberately does NOT call the existing `refreshUser()` context method for
  this path — that function also rotates the request ID, correct for a real
  session-start event (login/signup/OAuth) but noise on a silent background
  poll.

**AC2 — write-side defense-in-depth**: reused the EXISTING `refreshUser()`
context method (already used by the OAuth callback flow) rather than adding
a new one — it already does "fetch + reconcile + return", exactly what a
call site needs. At both `NewThreadPage.handleSubmit` and
`ThreadDetailPage.handleReply`, after a successful create: capture the
acting username before the write, call `refreshUser()` after, compare. The
write already happened by then (TOCTOU, per advisor) — accepted per AC2's
own wording ("either posts under the displayed user OR forces the identity
refresh"), so on a drift: `NewThreadPage` skips the auto-navigate and shows
an on-page notice (mirrors the existing `submittedPending` pattern) with a
manual link to the new topic; `ThreadDetailPage` skips the silent "Reply
posted." screen-reader announce (exactly how the live incident went
unnoticed) and shows a distinct notice via the existing `notice` state slot
instead.

**AC3 — Vitest coverage**: 6 new tests in `AuthContext.test.tsx` (changed
identity on focus, on visibilitychange, no-op when hidden, 401→logged-out
reflected, debounce blocks a rapid second focus, unchanged identity keeps
the same object reference) + 1 each in `NewThreadPage.test.tsx` /
`ThreadDetailPage.test.tsx` for the write-defense notice. Both pre-existing
test files needed a `useAuth` mock update to supply `refreshUser` (was
entirely unmocked in `NewThreadPage.test.tsx`, causing the newly-added
`useAuth()` call to throw "must be used within an AuthProvider" until
fixed) — all pre-existing tests in both files still pass unchanged once the
mock resolves to the SAME identity (no drift → normal success path).

**AC1's literal criterion is a two-tab browser repro** ("re-log-in as user
B in a second tab, focus the first tab"). Per advisor: no browser session
ran this session, and AC3 explicitly sanctions the Vitest/jsdom proxy
("mocked fetch identity change → context update") as the verification
method — flipped AC1 on that basis. The manual two-tab browser repro was
NOT executed; stating this plainly rather than letting the checkbox imply
otherwise.

Mutation-tested both the focus-reconciliation logic (AuthContext.tsx) and
one write-defense call site (NewThreadPage.tsx) — see command output below.

Verification:

```
$ ./node_modules/.bin/vitest run src/contexts/AuthContext.test.tsx src/pages/forum/NewThreadPage.test.tsx src/pages/forum/ThreadDetailPage.test.tsx
Test Files  3 passed (3)
Tests  98 passed (98)
$ ./node_modules/.bin/vitest run
Test Files  80 passed (80)
Tests  905 passed (905)
$ npx tsc --noEmit
(clean)
$ npm run lint
0 errors (1 pre-existing warning in coverage/block-navigation.js, unrelated)
```

Mutation tests (both restored + re-verified green):
- `AuthContext.tsx`'s `setUser((prevUser) => prevUser)` (dropped the
  username-comparison reconciliation entirely) → 3 of 6 focus tests
  correctly went red (the 3 that depend on reconciliation; the debounce and
  reference-stability tests correctly stayed green, since they don't
  exercise that branch).
- `NewThreadPage.tsx`'s drift-check replaced with an unconditional
  `navigate(path)` → the identity-drift test correctly went red (notice
  never appeared, navigated as if nothing happened).

### 2026-08-17 - Code review

Dispatched `react-typescript-reviewer` directly (single-domain diff). 8
findings — 6 accepted+fixed (3 were the same root cause), 1 accepted but
deliberately left unfixed (matches an existing file-wide pattern), 1
implicitly resolved by the same refactor as the others.

1. **[medium ×3, accepted, same root cause]** The identity comparison in
   `AuthContext.tsx`'s focus effect, `NewThreadPage.tsx`, and
   `ThreadDetailPage.tsx` all keyed off `User.username` — optional on the
   type (`username?: string`) — rather than `User.id` (required). A
   response missing `username` would silently disable drift detection.
   Verified against `types/auth.ts` before accepting. Fixed by switching
   all three comparisons to `.id`, keeping `.username` only for notice/
   display copy.
2. **[low, accepted]** Reusing the context's `refreshUser()` for the
   write-defense checks rotates the request ID on *every* successful
   forum write (not just a detected drift) — directly inconsistent with
   this same PR's own stated reason for NOT using `refreshUser()` in the
   focus-poll effect (tracing noise). Fixed by extracting a new shared
   `revalidateIdentity()` context method (`getCurrentUser` + id-based
   reconcile, no rotation) — used by both the focus effect (removing its
   inline duplicate) and both write call sites. This one refactor also
   resolved finding #1 in a single place instead of three.
3. **[medium ×2, accepted]** The write-defense drift check only ran in the
   `published` branch — a *pending* (moderation-queued) topic/reply
   created under a drifted identity went undetected, silently landing in
   the wrong user's moderation queue. Fixed: the `actingUserId`/
   `revalidateIdentity()` check now runs unconditionally before branching
   on `published`/`pending` in both `NewThreadPage.handleSubmit` and
   `ThreadDetailPage.handleReply`; a pending+drifted write shows a
   combined notice (drift copy + "awaiting moderation"), and
   `NewThreadPage`'s notice no longer assumes a live URL exists (`path` is
   now nullable — points at the board instead when pending).
4. **[low, accepted]** `identityDrift`'s inline `{path, asUsername}` type
   literal was inconsistent with this file's own `IdentificationHandoff`
   named-interface convention. Fixed: extracted `IdentityDrift` (now also
   carrying `pending: boolean` per finding #3's fix).
5. **[low, accepted-not-fixed]** No unmount guard on the focus effect's
   async `getCurrentUser()` chain. Verified against the sibling `initAuth`
   effect in the SAME file before deciding — it has the identical shape
   (no `ignore` flag either), so this is a pre-existing file-wide pattern,
   not new risk. `AuthProvider` is a root-level provider that essentially
   never unmounts mid-session, and React 18+ safely no-ops (dev-warn only)
   a post-unmount `setState`. Fixing only the NEW effect while leaving the
   identical pre-existing one alone would be an inconsistent, cosmetic
   asymmetry — left both as-is rather than partially patching.

Re-verified after all repairs (added 2 more tests for the newly-covered
pending+drift branches; mutation-tested the pending-branch logic too —
see below):

```
$ ./node_modules/.bin/vitest run src/contexts/AuthContext.test.tsx src/pages/forum/NewThreadPage.test.tsx src/pages/forum/ThreadDetailPage.test.tsx
Test Files  3 passed (3)
Tests  100 passed (100)
$ ./node_modules/.bin/vitest run
Test Files  80 passed (80)
Tests  907 passed (907)
$ npx tsc --noEmit / npm run lint
clean (0 errors; 1 pre-existing warning, unrelated)
```

Mutation-tested the new pending-branch drift logic (`NewThreadPage.tsx`'s
`drifted` hardcoded to `false`) → both the published-drift AND the new
pending-drift test correctly went red; restored, re-verified green.

## Notes

P3: requires multi-account switching in one profile to trigger, but the
failure mode (posting as the wrong account) is nasty when it hits. Surfaced
during the same session as PR #530.
